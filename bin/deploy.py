#!/usr/bin/env python

import os
import sys
import yaml
import boto3
import argparse
from botocore.exceptions import ClientError
import mimetypes
from boto3.s3.transfer import TransferConfig, S3Transfer
from threading import Lock
import time
import hashlib

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

class Deployer:
    def __init__(self, config):
        self.config = config
        self.session = boto3.Session(
            aws_access_key_id=self.config['aws']['access_key_id'],
            aws_secret_access_key=self.config['aws']['secret_access_key'],
            region_name=self.config['aws']['region']
        )
        self.s3 = self.session.resource('s3')
        self.cloudfront = self.session.client('cloudfront')
        self.bucket_name = self.config['aws']['s3']['bucket_name']
        self.bucket = self.s3.Bucket(self.bucket_name)
        self.distribution_id = self.config['aws']['cloudfront'].get('distribution_id')
        self.default_root_object = self.config['aws']['cloudfront'].get('default_root_object', 'index.html')
        self.transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,  # 8MB
            max_concurrency=10,
            use_threads=True
        )
        self.transfer_manager = S3Transfer(self.s3.meta.client, config=self.transfer_config)
        self.print_lock = Lock()
        self.changed_files = set()

    def check_aws_access(self):
        try:
            self.s3.meta.client.head_bucket(Bucket=self.bucket_name)
            if self.distribution_id:
                self.cloudfront.get_distribution(Id=self.distribution_id)
            return True
        except ClientError as e:
            print(f"Error accessing AWS resources: {e}")
            return False

    def guess_content_type(self, file_path):
        content_type, _ = mimetypes.guess_type(file_path)
        return content_type or 'application/octet-stream'

    def sync_directory(self, local_dir):
        local_dir = os.path.abspath(local_dir)
        
        # Upload local files to S3
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                s3_key = os.path.relpath(local_path, local_dir).replace("\\", "/")
                
                # Check if file needs to be uploaded
                try:
                    s3_obj = self.bucket.Object(s3_key)
                    s3_obj.load()
                    if s3_obj.content_length == os.path.getsize(local_path):
                       #if s3_obj.e_tag.strip('"') == self.get_local_etag(local_path):
                        with self.print_lock:
                            print(f"Skipped (unchanged): {s3_key}")
                        continue
                    else:
                        pass
                except ClientError:
                    # Object doesn't exist in S3, will be uploaded
                    pass

                # Upload file
                extra_args = {'ContentType': self.guess_content_type(local_path)}
                self.transfer_manager.upload_file(
                    local_path, self.bucket_name, s3_key,
                    extra_args=extra_args
                )
                self.changed_files.add('/' + s3_key)
                with self.print_lock:
                    print(f"Uploaded: {s3_key}")

        # Delete objects in S3 that don't exist locally
        for obj in self.bucket.objects.all():
            local_path = os.path.join(local_dir, obj.key)
            if not os.path.exists(local_path):
                obj.delete()
                self.changed_files.add('/' + obj.key)
                with self.print_lock:
                    print(f"Deleted: {obj.key}")

    def get_local_etag(self, file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def invalidate_cloudfront(self):
        self.changed_files.add('/')
        
        if not self.distribution_id:
            print("No CloudFront distribution ID in config, skipping invalidation.")
            return
        if not self.changed_files:
            print("No files changed, skipping CloudFront invalidation.")
            return

        print("Invalidating CloudFront cache...")
        try:
            paths_to_invalidate = list(self.changed_files) 
            if self.default_root_object in paths_to_invalidate:
                paths_to_invalidate.append('/')  # Invalidate root when default object changes
            
            response = self.cloudfront.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths_to_invalidate),
                        'Items': paths_to_invalidate
                    },
                    'CallerReference': str(time.time())
                }
            )
            invalidation_id = response['Invalidation']['Id']
            print(f"Invalidation created. ID: {invalidation_id}")
            self.wait_for_invalidation(invalidation_id)
        except ClientError as e:
            print(f"Error creating CloudFront invalidation: {e}")

    def wait_for_invalidation(self, invalidation_id):
        print("Waiting for invalidation to complete...")
        waiter = self.cloudfront.get_waiter('invalidation_completed')
        try:
            waiter.wait(
                DistributionId=self.distribution_id,
                Id=invalidation_id,
                WaiterConfig={
                    'Delay': 20,
                    'MaxAttempts': 30
                }
            )
            print("Invalidation completed successfully.")
        except Exception as e:
            print(f"Error waiting for invalidation to complete: {e}")

    def deploy(self):
        print("*** Starting deployment process...")
        if not self.check_aws_access():
            print("Deployment aborted.")
            return

        # Sync files to S3
        self.sync_directory(os.path.join(self.config['output_path'], 'public_html'))
        
        # Invalidate CloudFront cache if distribution ID is provided
        if self.distribution_id:
            self.invalidate_cloudfront()
        else:
            print("No CloudFront distribution ID provided in config. Skipping invalidation.")

        print("Deployment completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Deploy static site to S3 and invalidate CloudFront if configured")
    args = parser.parse_args()

    try:
        config = load_config()
        deployer = Deployer(config)
        deployer.deploy()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
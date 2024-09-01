#!/usr/bin/env python

import os
import sys
import yaml
import boto3
import argparse
import time
from botocore.exceptions import ClientError
import mimetypes

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

class S3CloudFrontDeployer:
    def __init__(self, config):
        self.config = config
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.config['aws']['access_key_id'],
            aws_secret_access_key=self.config['aws']['secret_access_key'],
            region_name=self.config['aws']['region']
        )
        self.cloudfront_client = boto3.client(
            'cloudfront',
            aws_access_key_id=self.config['aws']['access_key_id'],
            aws_secret_access_key=self.config['aws']['secret_access_key'],
            region_name=self.config['aws']['region']
        )
        self.bucket_name = self.config['aws']['s3']['bucket_name']
        self.distribution_id = self.config['aws']['cloudfront']['distribution_id']

    def check_bucket_access(self):
        try:
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            return True
        except ClientError as e:
            print(f"Error accessing bucket {self.bucket_name}: {e}")
            return False

    def get_s3_files(self):
        s3_files = {}
        paginator = self.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.bucket_name):
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_files[obj['Key']] = obj['Size']
        return s3_files

    def guess_content_type(self, file_path):
        content_type, _ = mimetypes.guess_type(file_path)
        if file_path.endswith('.html') or file_path.endswith('.htm'):
            return 'text/html'
        return content_type or 'application/octet-stream'

    def sync_directory(self, local_dir):
        s3_files = self.get_s3_files()
        local_files = set()
        changed_files = []

        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                s3_path = relative_path.replace("\\", "/")  # Ensure proper S3 key format
                local_size = os.path.getsize(local_path)
                local_files.add(s3_path)

                content_type = self.guess_content_type(local_path)
                if s3_path not in s3_files or s3_files[s3_path] != local_size:
                    self.s3_client.upload_file(
                        local_path, 
                        self.bucket_name, 
                        s3_path,
                        ExtraArgs={'ContentType': content_type}
                    )
                    print(f"Uploaded: {s3_path} (Content-Type: {content_type})")
                    changed_files.append(f'/{s3_path}')
                else:
                    # Check if content type needs updating
                    s3_object = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_path)
                    if s3_object.get('ContentType') != content_type:
                        self.s3_client.copy_object(
                            Bucket=self.bucket_name,
                            CopySource={'Bucket': self.bucket_name, 'Key': s3_path},
                            Key=s3_path,
                            MetadataDirective='REPLACE',
                            ContentType=content_type
                        )
                        print(f"Updated Content-Type: {s3_path} (Content-Type: {content_type})")
                        changed_files.append(f'/{s3_path}')
                    else:
                        print(f"Skipped (unchanged): {s3_path}")

        # Delete files that exist in S3 but not locally
        for s3_path in s3_files:
            if s3_path not in local_files:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
                print(f"Deleted: {s3_path}")
                changed_files.append(f'/{s3_path}')

        return changed_files

    def invalidate_cloudfront(self, changed_files):
        if not changed_files:
            print("No files changed. Skipping CloudFront invalidation.")
            return

        try:
            response = self.cloudfront_client.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(changed_files),
                        'Items': changed_files
                    },
                    'CallerReference': str(int(time.time()))
                }
            )
            invalidation_id = response['Invalidation']['Id']
            print(f"CloudFront invalidation created. Invalidation ID: {invalidation_id}")
        except ClientError as e:
            print(f"Error creating CloudFront invalidation: {e}")

    def deploy(self):
        print("*** Deploying to S3...")
        if not self.check_bucket_access():
            print("Deployment aborted.")
            return
        changed_files = self.sync_directory(os.path.join(self.config['output_path'], 'public_html'))
        print("S3 deployment completed successfully.")

        print("*** Invalidating CloudFront cache...")
        self.invalidate_cloudfront(changed_files)
        print("Deployment and invalidation process completed.")

def main():
    parser = argparse.ArgumentParser(description="Deploy static site to S3 and invalidate CloudFront")
    args = parser.parse_args()

    try:
        config = load_config()
        deployer = S3CloudFrontDeployer(config)
        deployer.deploy()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
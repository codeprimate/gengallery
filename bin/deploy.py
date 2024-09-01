#!/usr/bin/env python

import os
import sys
import yaml
import boto3
import argparse
from botocore.exceptions import ClientError

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

class S3Deployer:
    def __init__(self, config):
        self.config = config
        print(self.config['aws'])
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.config['aws']['access_key_id'],
            aws_secret_access_key=self.config['aws']['secret_access_key'],
            region_name=self.config['aws']['region']
        )
        self.bucket_name = self.config['aws']['bucket_name']

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

    def sync_directory(self, local_dir):
        s3_files = self.get_s3_files()
        local_files = set()

        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_dir)
                s3_path = relative_path.replace("\\", "/")  # Ensure proper S3 key format
                local_size = os.path.getsize(local_path)
                local_files.add(s3_path)

                if s3_path not in s3_files or s3_files[s3_path] != local_size:
                    self.s3_client.upload_file(local_path, self.bucket_name, s3_path)
                    print(f"Uploaded: {s3_path}")
                else:
                    print(f"Skipped (unchanged): {s3_path}")

        # Delete files that exist in S3 but not locally
        for s3_path in s3_files:
            if s3_path not in local_files:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
                print(f"Deleted: {s3_path}")

    def deploy(self):
        print("*** Deploying to S3...")
        if not self.check_bucket_access():
            print("Deployment aborted.")
            return
        self.sync_directory(os.path.join(self.config['output_path'], 'public_html'))
        print("Deployment completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Deploy static site to S3")
    args = parser.parse_args()

    try:
        config = load_config()
        deployer = S3Deployer(config)
        deployer.deploy()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
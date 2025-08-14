import json
import string
import random
import frappe
import boto3
import os
from botocore.exceptions import ClientError
from pathlib import Path


def generate_bucket_name(site_name):
    """Tạo tên bucket S3 duy nhất cho từng site"""
    # Loại bỏ dấu chấm và thay bằng dấu gạch ngang vì tên bucket S3 không được chứa dấu chấm
    safe_site_name = site_name.replace('.', '-').replace('_', '-').lower()
    
    # Thêm hậu tố ngẫu nhiên để đảm bảo không trùng lặp
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    bucket_name = f"nextgrp-{safe_site_name}-{random_suffix}"
    
    # Đảm bảo tên bucket tuân thủ quy định của S3 (3-63 ký tự)
    if len(bucket_name) > 63:
        bucket_name = bucket_name[:63]
    
    return bucket_name


def get_s3_credentials():
    """Lấy thông tin xác thực S3 từ cấu hình chung hoặc biến môi trường"""
    try:
        # Ưu tiên lấy từ cấu hình chung của site
        common_config = frappe.get_common_site_config()
        
        aws_access_key = common_config.get('aws_access_key_id')
        aws_secret_key = common_config.get('aws_secret_access_key')
        aws_s3_endpoint_url = common_config.get('aws_s3_endpoint_url')
        
        if not aws_access_key or not aws_secret_key:
            # Nếu không có, lấy từ biến môi trường hệ thống
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_s3_endpoint_url = os.getenv('AWS_S3_ENDPOINT_URL')

        if not aws_access_key or not aws_secret_key:
            return None
            
        return {
            'aws_access_key_id': aws_access_key,
            'aws_secret_access_key': aws_secret_key,
            'aws_s3_endpoint_url': aws_s3_endpoint_url
        }
    except Exception as e:
        frappe.log_error(f"Lỗi khi lấy thông tin S3: {str(e)}", "S3 Auto Setup")
        return None


def create_s3_bucket(bucket_name):
    """Tạo một S3 bucket với tên chỉ định"""
    try:
        credentials = get_s3_credentials()
        if not credentials:
            return False, "Không tìm thấy thông tin xác thực S3"
        
        # Tạo đối tượng S3 client
        s3_client_kwargs = {
            'aws_access_key_id': credentials['aws_access_key_id'],
            'aws_secret_access_key': credentials['aws_secret_access_key'],
        }
        
        # Thêm endpoint_url nếu có (cho Viettel Cloud hoặc S3-compatible services)
        if credentials.get('aws_s3_endpoint_url'):
            s3_client_kwargs['endpoint_url'] = credentials['aws_s3_endpoint_url']
            
        s3_client = boto3.client('s3', **s3_client_kwargs)
        
        # Kiểm tra xem bucket đã tồn tại chưa
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            return True, f"Bucket {bucket_name} đã tồn tại"
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # Bucket chưa tồn tại → tiếp tục tạo
                pass
            else:
                return False, f"Lỗi kiểm tra bucket: {str(e)}"
        
        # Tạo bucket - Viettel Cloud không cần CreateBucketConfiguration
        try:
            s3_client.create_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyExists':
                return True, f"Bucket {bucket_name} đã tồn tại"
            elif error_code == 'BucketAlreadyOwnedByYou':
                return True, f"Bucket {bucket_name} đã được bạn sở hữu"
            else:
                return False, f"Lỗi tạo bucket: {e.response['Error']['Message']}"
        
        return True, f"Đã tạo bucket {bucket_name} thành công"
        
    except ImportError as ie:
        return False, "Chưa cài đặt thư viện boto3. Cần chạy: pip install boto3"
    except Exception as e:
        return False, f"Lỗi khi tạo bucket: {str(e)}"


def setup_s3_for_site(site_name):
    """Tạo S3 bucket và trả về cấu hình để lưu vào site_config.json"""
    try:
        credentials = get_s3_credentials()
        if not credentials:
            return None
        
        # Sinh tên bucket
        bucket_name = generate_bucket_name(site_name)
        
        # Tạo bucket
        success, message = create_s3_bucket(bucket_name)
        
        if success:
            # Trả về cấu hình S3 để thêm vào site_config.json
            s3_config = {
                's3_bucket': bucket_name,
                'aws_access_key_id': credentials['aws_access_key_id'],
                'aws_secret_access_key': credentials['aws_secret_access_key'],
                'aws_s3_endpoint_url': credentials['aws_s3_endpoint_url'],
            }
            
            return s3_config
        else:
            frappe.log_error(f"Không thể tạo bucket S3 cho site {site_name}: {message}", "S3 Auto Setup")
            return None
            
    except Exception as e:
        frappe.log_error(f"Lỗi khi thiết lập S3 cho site {site_name}: {str(e)}", "S3 Auto Setup")
        return None


def add_s3_to_site_config(site_name, s3_config):
    """Thêm cấu hình S3 vào file site_config.json của site"""
    try:
        site_config_path = Path(frappe.get_site_path("site_config.json"), site=site_name)

        if site_config_path.exists():
            with open(site_config_path, 'r') as f:
                current_config = json.load(f)
        else:
            current_config = {}
        
        # Thêm các thông tin cấu hình S3 vào
        current_config.update(s3_config)
        
        # Ghi lại file site_config.json
        with open(site_config_path, 'w') as f:
            json.dump(current_config, f, indent=2, sort_keys=True)

        return True

    except Exception as e:
        frappe.log_error(f"Lỗi khi ghi site_config cho site {site_name}: {str(e)}", "S3 Auto Setup")
        return False


def test_s3_connection():
    """Test kết nối S3 với credentials hiện tại"""
    try:
        credentials = get_s3_credentials()
        if not credentials:
            return False, "Không tìm thấy thông tin xác thực S3"
        
        # Tạo S3 client để test
        s3_client_kwargs = {
            'aws_access_key_id': credentials['aws_access_key_id'],
            'aws_secret_access_key': credentials['aws_secret_access_key'],
        }
        
        if credentials.get('aws_s3_endpoint_url'):
            s3_client_kwargs['endpoint_url'] = credentials['aws_s3_endpoint_url']
            
        s3_client = boto3.client('s3', **s3_client_kwargs)
        
        # Test bằng cách list buckets
        s3_client.list_buckets()
        return True, "Kết nối S3 thành công"
        
    except Exception as e:
        return False, f"Lỗi kết nối S3: {str(e)}"
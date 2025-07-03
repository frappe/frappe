import frappe
import boto3
import os
import uuid
from datetime import datetime
from io import BytesIO


def write_file_to_s3(file_doc):
    """
    Trình xử lý tệp lưu trữ lên S3 cho Frappe, thay thế cơ chế ghi tệp mặc định
    """
    s3_config = get_s3_config()
    if not s3_config:
        # Fallback: Nếu S3 fail → lưu local
        return file_doc.save_file_on_filesystem()
    
    try:
        # Kết nối S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=s3_config['aws_access_key_id'],
            aws_secret_access_key=s3_config['aws_secret_access_key'],
            endpoint_url=s3_config.get('aws_s3_endpoint_url'),
            region_name=s3_config.get('aws_default_region', 'us-east-1')
        )
        
        # Tạo S3 key
        s3_key = generate_s3_key(file_doc.file_name)
        
        # Kiểm tra kích thước tệp để tải lên (>50MB)
        file_size = len(file_doc._content)
        chunk_threshold = 50 * 1024 * 1024  # 50MB
        
        if file_size > chunk_threshold:
            # Sử dụng tải lên nhiều phần cho các tệp lớn
            return upload_large_file_to_s3(file_doc, s3_client, s3_config, s3_key)
        else:
            # Xử lý tải lên các tệp nhỏ
            return upload_small_file_to_s3(file_doc, s3_client, s3_config, s3_key)
        
    except Exception as e:
        frappe.logger().error(f"Failed to upload {file_doc.file_name} to S3: {str(e)}")
        return file_doc.save_file_on_filesystem()


def upload_small_file_to_s3(file_doc, s3_client, s3_config, s3_key):
    """Tải lên các tệp nhỏ (<50MB) trong một request duy nhất"""
    s3_client.upload_fileobj(
        BytesIO(file_doc._content), 
        s3_config['s3_bucket'], 
        s3_key,
        ExtraArgs={
            'ContentType': file_doc.content_type or 'application/octet-stream',
            'Metadata': {
                'original_filename': file_doc.file_name,
                'uploaded_by': frappe.session.user
            }
        }
    )
    
    # Set S3 URL
    file_doc.file_url = generate_s3_url(s3_config, s3_key)
    file_doc.is_private = 0
    
    frappe.logger().info(f"File {file_doc.file_name} uploaded to S3: {file_doc.file_url}")
    
    return {
        "file_name": file_doc.file_name,
        "file_url": file_doc.file_url
    }


def upload_large_file_to_s3(file_doc, s3_client, s3_config, s3_key):
    """Upload các tệp lớn (>50MB) bằng cách sử dụng tải lên nhiều phần"""
    # Bắt đầu tải lên nhiều phần
    response = s3_client.create_multipart_upload(
        Bucket=s3_config['s3_bucket'],
        Key=s3_key,
        ContentType=file_doc.content_type or 'application/octet-stream',
        Metadata={
            'original_filename': file_doc.file_name,
            'uploaded_by': frappe.session.user
        }
    )
    
    upload_id = response['UploadId']
    parts = []
    chunk_size = 5 * 1024 * 1024
    
    try:
        # Tải tệp lên theo từng phần
        content = file_doc._content
        for i, chunk_start in enumerate(range(0, len(content), chunk_size)):
            chunk_end = min(chunk_start + chunk_size, len(content))
            chunk_data = content[chunk_start:chunk_end]
            
            part_response = s3_client.upload_part(
                Bucket=s3_config['s3_bucket'],
                Key=s3_key,
                PartNumber=i + 1,
                UploadId=upload_id,
                Body=chunk_data
            )
            
            parts.append({
                'ETag': part_response['ETag'],
                'PartNumber': i + 1
            })
            
            # Log progress cho các tệp lớn
            progress = (chunk_end / len(content)) * 100
            if i % 5 == 0:  # Log mỗi 5 chunk
                frappe.logger().info(f"Upload progress for {file_doc.file_name}: {progress:.1f}%")
        
        # Hoàn tất tải lên nhiều phần
        s3_client.complete_multipart_upload(
            Bucket=s3_config['s3_bucket'],
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        
        # Set S3 URL
        file_doc.file_url = generate_s3_url(s3_config, s3_key)
        file_doc.is_private = 0
        
        frappe.logger().info(f"Large file {file_doc.file_name} uploaded to S3 successfully: {file_doc.file_url}")
        
        return {
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url
        }
        
    except Exception as e:
        # Hủy bỏ việc tải lên nhiều phần khi có lỗi
        try:
            s3_client.abort_multipart_upload(
                Bucket=s3_config['s3_bucket'],
                Key=s3_key,
                UploadId=upload_id
            )
        except:
            pass
        raise e


def generate_s3_url(s3_config, s3_key):
    """Tạo URL S3 dựa trên cấu hình endpoint"""
    if s3_config.get('aws_s3_endpoint_url') and 'amazonaws.com' not in s3_config['aws_s3_endpoint_url']:
        # Custom S3 endpoint
        return f"{s3_config['aws_s3_endpoint_url']}/{s3_config['s3_bucket']}/{s3_key}"
    else:
        # AWS S3
        return f"https://{s3_config['s3_bucket']}.s3.amazonaws.com/{s3_key}"


def delete_file_from_s3(file_doc, only_thumbnail=False):
    """ Xóa các tập tin khỏi S3 """
    s3_config = get_s3_config()
    if not s3_config:
        # Fallback: Quay lại xóa mặc định
        return file_doc.delete_file_from_filesystem(only_thumbnail=only_thumbnail)
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=s3_config['aws_access_key_id'],
            aws_secret_access_key=s3_config['aws_secret_access_key'],
            endpoint_url=s3_config.get('aws_s3_endpoint_url'),
            region_name=s3_config.get('aws_default_region', 'us-east-1')
        )
        
        # Trích xuất S3 key từ file_url
        if file_doc.file_url and ('s3' in file_doc.file_url.lower() or 'amazonaws' in file_doc.file_url.lower()):
            s3_key = extract_s3_key_from_url(file_doc.file_url, s3_config['s3_bucket'])
            if s3_key:
                s3_client.delete_object(Bucket=s3_config['s3_bucket'], Key=s3_key)
                frappe.logger().info(f"Deleted {file_doc.file_name} from S3")
        
        # Xử lý hình thu nhỏ nếu cần
        if file_doc.thumbnail_url and not only_thumbnail:
            thumbnail_key = extract_s3_key_from_url(file_doc.thumbnail_url, s3_config['s3_bucket'])
            if thumbnail_key:
                s3_client.delete_object(Bucket=s3_config['s3_bucket'], Key=thumbnail_key)
        
    except Exception as e:
        frappe.logger().error(f"Failed to deletto filesystem deletione {file_doc.file_name} from S3: {str(e)}")
        # Fallback: Quay lại xóa hệ thống tập tin
        file_doc.delete_file_from_filesystem(only_thumbnail=only_thumbnail)


def get_s3_config():
    """Nhận cấu hình S3 từ site_config"""
    conf = frappe.local.conf
    
    required_keys = ['s3_bucket', 'aws_access_key_id', 'aws_secret_access_key']
    
    # Kiểm tra xem tất cả cấu hình S3 cần thiết có tồn tại không
    if not all(conf.get(key) for key in required_keys):
        return None
    
    return {
        's3_bucket': conf.get('s3_bucket'),
        'aws_access_key_id': conf.get('aws_access_key_id'),
        'aws_secret_access_key': conf.get('aws_secret_access_key'),
        'aws_s3_endpoint_url': conf.get('aws_s3_endpoint_url'),
        'aws_default_region': conf.get('aws_default_region', 'us-east-1')
    }


def generate_s3_key(filename):
    # Tạo cấu trúc thư mục: year/month/uuid_filename
    now = datetime.now()
    folder = f"{now.year}/{now.month:02d}"
    
    # Thêm UUID vào tên tệp để tránh conflicts
    name, ext = os.path.splitext(filename)
    unique_filename = f"{uuid.uuid4().hex[:8]}_{name}{ext}"
    
    return f"{folder}/{unique_filename}"


def extract_s3_key_from_url(file_url, bucket_name):
    """Extract S3 key from S3 URL"""
    try:
        if f"{bucket_name}.s3.amazonaws.com" in file_url:
            return file_url.split(f"{bucket_name}.s3.amazonaws.com/")[1]
        elif f"s3.amazonaws.com/{bucket_name}" in file_url:
            return file_url.split(f"s3.amazonaws.com/{bucket_name}/")[1]
        else:
            parts = file_url.split(f"/{bucket_name}/")
            if len(parts) > 1:
                return parts[1]
    except:
        pass
    return None


@frappe.whitelist()
def test_s3_connection():
    """Kiểm tra kết nối S3 qua API"""
    s3_config = get_s3_config()
    if not s3_config:
        return {"status": "error", "message": "S3 config not found"}
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=s3_config['aws_access_key_id'],
            aws_secret_access_key=s3_config['aws_secret_access_key'],
            endpoint_url=s3_config.get('aws_s3_endpoint_url'),
            region_name=s3_config.get('aws_default_region', 'us-east-1')
        )
        
        # Kiểm tra bằng cách liệt kê các buckets
        response = s3_client.list_buckets()
        buckets = [b['Name'] for b in response['Buckets']]
        
        return {
            "status": "success", 
            "message": "S3 connection successful",
            "buckets": buckets,
            "target_bucket": s3_config['s3_bucket']
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
import frappe
from frappe.utils.s3_auto_setup import setup_s3_for_site, add_s3_to_site_config, get_s3_credentials


def setup_s3_for_new_site():
    """
    Hook được gọi sau khi cài đặt frappe app vào site mới
    Tự động tạo S3 bucket và cấu hình cho site
    """
    try:
        # Kiểm tra xem có thông tin xác thực AWS không
        credentials = get_s3_credentials()
        if not credentials:
            return

        site_name = frappe.local.site
        
        # Kiểm tra xem site đã có cấu hình S3 chưa
        site_config = frappe.conf
        if site_config.get('s3_bucket'):
            print(f"Site {site_name} đã có S3 bucket: {site_config.get('s3_bucket')}")
            return

        # Tạo S3 bucket cho site mới
        s3_config = setup_s3_for_site(site_name)

        if s3_config:
            # Thêm thông tin cấu hình S3 vào file site_config.json
            success = add_s3_to_site_config(site_name, s3_config)
            
            if success:
                print(f"Đã tạo và cấu hình S3 bucket '{s3_config['s3_bucket']}' cho site {site_name}")
            else:
                print(f"Cảnh báo: Không thể cập nhật site_config.json cho site {site_name}")
        else:
            # Nếu có thông tin AWS nhưng tạo bucket thất bại, hiển thị cảnh báo
            if credentials:
                print(f"Cảnh báo: Không thể tạo S3 bucket cho site {site_name}. Kiểm tra quyền truy cập AWS.")
                
    except ImportError:
        pass
    except Exception as e:
        frappe.log_error(f"Lỗi khi thêm cấu hình S3 cho site {frappe.local.site}: {str(e)}", "S3 Auto Setup")
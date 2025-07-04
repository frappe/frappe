import frappe.installer
from frappe.installer import make_site_config as original_make_site_config
from frappe.utils.s3_auto_setup import setup_s3_for_site, add_s3_to_site_config, get_s3_credentials

def execute():
    """Cập nhật Frappe installer để tự động tạo S3 bucket cho site mới"""

    def patched_make_site_config(
        db_name=None,
        db_password=None,
        site_config=None,
        db_type=None,
        db_socket=None,
        db_host=None,
        db_port=None,
    ):
        """Phiên bản đã được vá của make_site_config để tự động thêm cấu hình S3"""

        # Gọi hàm gốc trước để tạo site config cơ bản
        original_make_site_config(
            db_name=db_name,
            db_password=db_password,
            site_config=site_config,
            db_type=db_type,
            db_socket=db_socket,
            db_host=db_host,
            db_port=db_port,
        )

        # Thêm cấu hình S3
        try:
            site_name = frappe.local.site
            if site_config and isinstance(site_config, dict) and site_config.get('s3_bucket'):
                return

            # Kiểm tra xem có thông tin xác thực AWS không
            if not get_s3_credentials():
                return

            # Tạo S3 bucket cho site mới
            s3_config = setup_s3_for_site(site_name)

            if s3_config:
                # Thêm thông tin cấu hình S3 vào file site_config.json
                success = add_s3_to_site_config(site_name, s3_config)
                if success:
                    print(f"✓ Đã tạo và cấu hình S3 bucket '{s3_config['s3_bucket']}' cho site {site_name}")
                else:
                    print(f"⚠ Cảnh báo: Không thể cập nhật site_config.json cho site {site_name}")
            else:
                # Nếu có thông tin AWS nhưng tạo bucket thất bại, hiển thị cảnh báo
                credentials = get_s3_credentials()
                if credentials:
                    print(f"⚠ Cảnh báo: Không thể tạo S3 bucket cho site {site_name}. Kiểm tra quyền truy cập AWS.")
                    
        except ImportError:
            # Chưa cài đặt boto3, bỏ qua không thông báo
            pass
        except Exception as e:
            frappe.log_error(f"Lỗi khi thêm cấu hình S3 cho site {frappe.local.site}: {str(e)}", "S3 Auto Setup")
            print(f"Cảnh báo: Có lỗi xảy ra khi thiết lập S3 cho site: {str(e)}")

    # Áp dụng bản vá
    frappe.installer.make_site_config = patched_make_site_config

    print("✓ Đã áp dụng bản vá tạo S3 tự động vào Frappe installer")
    print("Khi tạo site mới bằng 'bench new-site' sẽ tự động có S3 bucket")

import frappe
from frappe import _
import os
from frappe.utils import get_site_path, get_files_path


@frappe.whitelist()
def get_site_storage_summary():
    """
    API tổng hợp storage usage từ tất cả các app trên site
    Trả về: {
        "total_usage": bytes,
        "limit": bytes, 
        "usage_percent": float,
        "breakdown": {
            "frappe_files": bytes,
            "drive_files": bytes, 
            "database": bytes,
            "backups": bytes
        },
        "apps_detail": [...]
    }
    """
    try:
        # Lấy giới hạn từ site_config
        site_config = frappe.get_site_config()
        plan_limit = site_config.get("plan_limit", {})
        storage_limit_mb = plan_limit.get("max_storage_usage", 0)  # MB
        storage_limit_bytes = storage_limit_mb * 1024 * 1024  # Convert to bytes
        
        # Tính toán storage usage từng app
        breakdown = {}
        apps_detail = []
        
        # 1. Frappe Core Files
        frappe_files_size = get_frappe_files_usage()
        breakdown["frappe_files"] = frappe_files_size
        apps_detail.append({
            "app": "frappe", 
            "doctype": "File",
            "usage_bytes": frappe_files_size,
            "usage_mb": round(frappe_files_size / (1024 * 1024), 2),
            "description": "Core files, attachments, uploads"
        })
        
        # 2. Drive App Files (nếu có)
        if frappe.db.exists("DocType", "Drive File"):
            drive_files_size = get_drive_files_usage()
            breakdown["drive_files"] = drive_files_size
            apps_detail.append({
                "app": "drive",
                "doctype": "Drive File", 
                "usage_bytes": drive_files_size,
                "usage_mb": round(drive_files_size / (1024 * 1024), 2),
                "description": "Drive app files and folders"
            })
        else:
            breakdown["drive_files"] = 0
            
        # 3. Database Size
        database_size = get_database_usage()
        breakdown["database"] = database_size
        apps_detail.append({
            "app": "system",
            "doctype": "Database",
            "usage_bytes": database_size,
            "usage_mb": round(database_size / (1024 * 1024), 2), 
            "description": "Database tables and indexes"
        })
        
        # 4. Backup Files
        backup_size = get_backup_usage()
        breakdown["backups"] = backup_size
        apps_detail.append({
            "app": "system",
            "doctype": "Backup",
            "usage_bytes": backup_size,
            "usage_mb": round(backup_size / (1024 * 1024), 2),
            "description": "Site backups"
        })
        
        # 5. NextGRP và các app khác (file attachments thuộc Frappe core)
        # Không cần tính riêng vì đã được tính trong frappe_files
        
        # Tổng hợp
        total_usage = sum(breakdown.values())
        usage_percent = (total_usage / storage_limit_bytes * 100) if storage_limit_bytes > 0 else 0
        
        return {
            "total_usage": total_usage,
            "total_usage_mb": round(total_usage / (1024 * 1024), 2),
            "total_usage_gb": round(total_usage / (1024 * 1024 * 1024), 2),
            "limit": storage_limit_bytes,
            "limit_mb": storage_limit_mb,
            "limit_gb": round(storage_limit_mb / 1024, 2),
            "usage_percent": round(usage_percent, 2),
            "remaining_bytes": max(0, storage_limit_bytes - total_usage),
            "remaining_mb": max(0, round((storage_limit_bytes - total_usage) / (1024 * 1024), 2)),
            "is_over_limit": total_usage > storage_limit_bytes,
            "breakdown": breakdown,
            "apps_detail": apps_detail
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_site_storage_summary: {str(e)}")
        return {
            "error": str(e),
            "total_usage": 0,
            "limit": 0,
            "usage_percent": 0,
            "breakdown": {},
            "apps_detail": []
        }


def get_frappe_files_usage():
    """Tính dung lượng file từ Frappe core File doctype"""
    try:
        # Tính từ database (nhanh hơn scan filesystem)
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(file_size), 0) as total_size 
            FROM `tabFile` 
            WHERE file_size > 0 AND is_folder = 0
        """)[0][0]
        
        return int(result or 0)
    except Exception as e:
        frappe.log_error(f"Error calculating Frappe files usage: {str(e)}")
        return 0


def get_drive_files_usage():
    """Tính dung lượng file từ Drive app"""
    try:
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(file_size), 0) as total_size 
            FROM `tabDrive File` 
            WHERE file_size > 0 AND is_group = 0 AND is_active = 1
        """)[0][0]
        
        return int(result or 0)
    except Exception as e:
        frappe.log_error(f"Error calculating Drive files usage: {str(e)}")
        return 0


def get_database_usage():
    """Tính dung lượng database"""
    try:
        if frappe.db.db_type == "mariadb":
            result = frappe.db.sql("""
                SELECT COALESCE(SUM(data_length + index_length), 0) as total_size
                FROM information_schema.TABLES 
                WHERE table_schema = DATABASE()
            """)[0][0]
        else:  # PostgreSQL
            result = frappe.db.sql("""
                SELECT COALESCE(SUM(pg_total_relation_size(schemaname||'.'||tablename)), 0) as total_size
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)[0][0]
            
        return int(result or 0)
    except Exception as e:
        frappe.log_error(f"Error calculating database usage: {str(e)}")
        return 0


def get_backup_usage():
    """Tính dung lượng backup files"""
    try:
        backup_path = get_site_path("private", "backups")
        if not os.path.exists(backup_path):
            return 0
            
        total_size = 0
        for root, dirs, files in os.walk(backup_path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
                    
        return total_size
    except Exception as e:
        frappe.log_error(f"Error calculating backup usage: {str(e)}")
        return 0


@frappe.whitelist()
def check_storage_quota(required_size_bytes=0):
    """
    Kiểm tra xem có đủ quota để upload file không
    Args:
        required_size_bytes: Dung lượng file cần upload (bytes)
    Returns:
        {
            "allowed": boolean,
            "message": string,
            "remaining_space": bytes
        }
    """
    try:
        storage_summary = get_site_storage_summary()
        
        if storage_summary.get("error"):
            return {"allowed": True, "message": "Cannot check quota", "remaining_space": 0}
            
        remaining_space = storage_summary["remaining_bytes"]
        
        if required_size_bytes <= remaining_space:
            return {
                "allowed": True,
                "message": "Sufficient storage space",
                "remaining_space": remaining_space
            }
        else:
            return {
                "allowed": False, 
                "message": f"Insufficient storage. Required: {required_size_bytes / (1024*1024):.2f} MB, Available: {remaining_space / (1024*1024):.2f} MB",
                "remaining_space": remaining_space
            }
            
    except Exception as e:
        frappe.log_error(f"Error in check_storage_quota: {str(e)}")
        return {"allowed": True, "message": f"Error checking quota: {str(e)}", "remaining_space": 0}


@frappe.whitelist()
def get_storage_breakdown_by_app():
    """
    API để lấy breakdown storage theo từng app chi tiết
    """
    try:
        apps_installed = frappe.get_installed_apps()
        app_breakdown = []
        
        for app in apps_installed:
            app_usage = get_app_storage_usage(app)
            if app_usage["total_usage"] > 0:
                app_breakdown.append(app_usage)
                
        # Sort theo usage giảm dần
        app_breakdown.sort(key=lambda x: x["total_usage"], reverse=True)
        
        return {
            "apps": app_breakdown,
            "total_apps": len(app_breakdown)
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_storage_breakdown_by_app: {str(e)}")
        return {"apps": [], "total_apps": 0}


def get_app_storage_usage(app_name):
    """Tính storage usage cho một app cụ thể"""
    try:
        app_usage = {
            "app_name": app_name,
            "total_usage": 0,
            "files_count": 0,
            "doctypes": []
        }
        
        # Lấy các doctype của app
        doctypes = frappe.get_all("DocType", 
            filters={"module": ["like", f"%{app_name.title()}%"]}, 
            fields=["name", "module"])
            
        for doctype in doctypes:
            # Tính file attachments cho doctype này
            file_usage = frappe.db.sql("""
                SELECT COUNT(*) as count, COALESCE(SUM(file_size), 0) as size
                FROM `tabFile` 
                WHERE attached_to_doctype = %s AND file_size > 0
            """, doctype.name)[0]
            
            if file_usage[1] > 0:  # Có file usage
                app_usage["doctypes"].append({
                    "doctype": doctype.name,
                    "files_count": file_usage[0],
                    "usage_bytes": file_usage[1],
                    "usage_mb": round(file_usage[1] / (1024 * 1024), 2)
                })
                app_usage["total_usage"] += file_usage[1]
                app_usage["files_count"] += file_usage[0]
        
        return app_usage
        
    except Exception as e:
        frappe.log_error(f"Error calculating storage for app {app_name}: {str(e)}")
        return {"app_name": app_name, "total_usage": 0, "files_count": 0, "doctypes": []} 
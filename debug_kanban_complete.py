#!/usr/bin/env python3
"""
Complete debug script to understand the kanban sorting issue
"""

import sys
import os
sys.path.append('/workspace/development/frappe-bench')
sys.path.append('/workspace/development/frappe-bench/apps/frappe')

# Try to import frappe and test the actual function
try:
    import frappe
    from frappe.desk.doctype.kanban_board.kanban_board import get_projects_ordered_by_queue_position_and_appointment_date
    
    def debug_actual_data():
        """Debug with actual data from the database"""
        print("=== DEBUGGING ACTUAL KANBAN DATA ===")
        
        try:
            # Get the actual projects data
            projects = get_projects_ordered_by_queue_position_and_appointment_date()
            
            print(f"Total projects found: {len(projects)}")
            
            # Filter for "In queue" status to match the image
            in_queue_projects = [p for p in projects if p.get('status') == 'In queue']
            
            print(f"Projects in 'In queue' status: {len(in_queue_projects)}")
            
            for i, project in enumerate(in_queue_projects[:10]):  # Show first 10
                print(f"{i+1}. {project.get('name')} - queue_pos: {project.get('queue_position')} - appointment_date: {project.get('appointment_date')}")
            
            # Look specifically for the problematic projects
            test_projects = [p for p in in_queue_projects if 'TEST' in p.get('name', '')]
            
            print(f"\n=== TEST PROJECTS (from image) ===")
            for project in test_projects:
                print(f"- {project.get('name')}: queue_pos={project.get('queue_position')}, appointment_date={project.get('appointment_date')}")
                
        except Exception as e:
            print(f"Error getting actual data: {e}")
            
    if __name__ == "__main__":
        debug_actual_data()
        
except ImportError as e:
    print(f"Cannot import frappe modules: {e}")
    print("This script needs to be run in the frappe environment")
    
    # Fallback to manual testing
    from datetime import datetime
    
    def manual_debug():
        """Manual debug with sample data"""
        print("=== MANUAL DEBUG (Sample Data) ===")
        
        # Sample data from the image
        test_projects = [
            {
                'queue_position': '1',
                'name': 'TEST18071',
                'status': 'In queue',
                'appointment_date': '2025-07-19'
            },
            {
                'queue_position': '1',
                'name': 'TEST07012',
                'status': 'In queue',
                'appointment_date': '2025-07-15'
            }
        ]
        
        def sort_key(project):
            status = project.get('status')
            
            if status in ["In queue", "In parking"]:
                # Convert queue_position
                queue_pos = project.get('queue_position')
                try:
                    queue_position_int = int(float(queue_pos))
                except (ValueError, TypeError):
                    queue_position_int = 999999
                
                # Handle appointment_date
                appointment_date = project.get('appointment_date')
                if appointment_date and appointment_date != 'None':
                    try:
                        if isinstance(appointment_date, str):
                            date_formats = ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y']
                            date_obj = None
                            for fmt in date_formats:
                                try:
                                    date_obj = datetime.strptime(appointment_date, fmt)
                                    break
                                except ValueError:
                                    continue
                            if date_obj is None:
                                date_obj = datetime(9999, 12, 31)
                        else:
                            date_obj = datetime(9999, 12, 31)
                        
                        print(f"DEBUG {project['name']}: queue_pos={queue_position_int}, date_obj={date_obj}")
                        return (queue_position_int, date_obj)
                    except Exception as e:
                        print(f"DEBUG {project['name']}: date error={e}")
                        return (queue_position_int, datetime(9999, 12, 31))
                else:
                    return (queue_position_int, datetime(9999, 12, 31))
            
            return (float('inf'), datetime(9999, 12, 31))
        
        print("Original order:")
        for project in test_projects:
            print(f"  {project['name']}: {project['appointment_date']}")
        
        sorted_projects = sorted(test_projects, key=sort_key)
        
        print("\nSorted order:")
        for project in sorted_projects:
            print(f"  {project['name']}: {project['appointment_date']}")
        
        print("\nExpected: TEST07012 (15-07) should come before TEST18071 (19-07)")
        actual_order = [p['name'] for p in sorted_projects]
        expected_order = ['TEST07012', 'TEST18071']
        
        if actual_order == expected_order:
            print("✅ SORTING IS CORRECT!")
        else:
            print("❌ SORTING IS WRONG!")
            print(f"Expected: {expected_order}")
            print(f"Actual:   {actual_order}")
    
    manual_debug()

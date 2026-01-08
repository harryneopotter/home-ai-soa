#!/usr/bin/env python3
"""
Safe History Update - Ensures History.md is appended to, not overwritten
"""

import os
from datetime import datetime

def safe_update_history(filepath='RemAssist/History.md', new_content='', session_num=None):
    """
    Safely update History.md by appending new content instead of overwriting.
    
    Args:
        filepath: Path to History.md
        new_content: New session content to add
        session_num: Optional session number for validation
    
    Returns:
        True if successful, False if error
    """
    
    # Validate session number if provided
    if session_num is not None:
        # Read existing file
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Find all existing sessions
            import re
            existing_sessions = re.findall(r'Session (\d+)', content)
            
            if existing_sessions:
                max_session = max(map(int, existing_sessions))
                
                # Validate new session number
                if session_num <= max_session:
                    print(f"⚠️  Error: Session {session_num} is not greater than max existing session {max_session}")
                    print("       This would create a gap or duplicate. Use next session number: {max_session + 1}")
                    return False
        
    # Append to file (create if doesn't exist)
    try:
        with open(filepath, 'a' if os.path.exists(filepath) else 'w') as f:
            if os.path.exists(filepath):
                f.write('\n\n')  # Add separator if appending
            f.write(new_content)
        
        print(f"✅ Successfully updated {filepath}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {filepath}: {e}")
        return False

def get_next_session_number(filepath='RemAssist/History.md'):
    """
    Get the next available session number to avoid gaps
    """
    if not os.path.exists(filepath):
        return 1
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    import re
    sessions = re.findall(r'Session (\d+)', content)
    
    if not sessions:
        return 1
    
    return max(map(int, sessions)) + 1

# Example usage
if __name__ == '__main__':
    # Get next session number
    next_session = get_next_session_number()
    print(f"Next session number: {next_session}")
    
    # Example: Add new session
    # new_content = f"### {datetime.now().strftime('%B %d, %Y')} - New Feature (Session {next_session})\n\n...content..."
    # safe_update_history(new_content=new_content, session_num=next_session)

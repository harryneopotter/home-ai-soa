📑 Finance Intelligence MVP: Comprehensive Report & Design
Date: December 24, 2025  
Project: SOA1 Daily Home Assistant — Finance Intelligence (v2)  
Status: Stage 2 Complete (Parser & Backend) | UI Pending
1. 🛠 Current Update Summary (Completed)
We have successfully built the Extraction Engine and the Upload Infrastructure. The system is now capable of receiving a PDF, identifying what it is, and preparing it for AI analysis.
Key Achievements:
*   Dual-GPU Orchestration: Configured src/models.py to route the NemoAgent (Orchestrator) to GPU 0 and Phinance-3b (Expert) to GPU 1. Verified both respond correctly.
*   Staged Parser (src/parser.py): Implemented a production-grade parser that:
    1.  Detects Identity: Detects if the document is an Apple Card, Chase, or generic statement.
    2.  Generates Summary: Uses NemoAgent to create a human-readable synopsis of the document structure.
    3.  Extracts Transactions: Uses high-speed Regex for known patterns with a chunked NemoAgent fallback for complex layouts.
*   Secure Upload Backend (main.py): Added a /upload route to the SOA Web UI that enforces PDF-only uploads and stores them with unique IDs for the finance agent to process.
---
2. 📋 The Plan (Next Steps)
Once the UI is applied, the workflow will follow this Staged Awareness path:
1.  Ingestion: User uploads a PDF via the Dashboard.
2.  Stage A (Silent): System runs get_identity_context to identify the user and bank.
3.  Stage B (Consent): System shows the user the Structural Summary.
    *   System: "I see a 5-page Chase statement for November. Should I extract the 42 transactions I've found?"
4.  Stage C (Execution): Upon user "Yes," the system runs extract_transactions and hands the data to Phinance-3b for categorization and insight generation.
---
3. 🎨 Web UI Design (Fully Coded)
This is the code to be inserted into /home/ryzen/projects/soa-webui/templates/index.html. It matches the existing "Tailscale Edition" aesthetic with gradients and white cards.
HTML/Jinja2 Snippet:
<!-- FINANCE UPLOAD MODULE: Place before "System Overview" -->
<div class="system-info">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
        <div style="background: #667eea; color: white; width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px;">
            📂
        </div>
        <h2 style="color: #333; margin-bottom: 0;">Finance Intelligence Ingest</h2>
    </div>
    <!-- Upload Status Feedback -->
    {% if upload_status == 'success' %}
    <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #c3e6cb; display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 20px;">✅</span>
        <div>
            <strong>Upload Successful!</strong><br>
            <span style="font-size: 12px; opacity: 0.8;">Document ID: <code>{{ upload_doc_id }}</code>. Waiting for your command to analyze.</span>
        </div>
    </div>
    {% elif upload_status == 'error' %}
    <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #f5c6cb; display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 20px;">❌</span>
        <div>
            <strong>Upload Failed</strong><br>
            <span style="font-size: 12px; opacity: 0.8;">Please ensure the file is a valid PDF and under 10MB.</span>
        </div>
    </div>
    {% endif %}
    <!-- Ingest Form -->
    <form action="/upload" method="post" enctype="multipart/form-data" style="display: flex; flex-direction: column; gap: 15px;">
        <div style="position: relative; border: 2px dashed #e0e0e0; border-radius: 12px; padding: 30px; text-align: center; transition: border-color 0.3s;" 
             onmouseover="this.style.borderColor='#667eea'" onmouseout="this.style.borderColor='#e0e0e0'">
            <input type="file" name="file" id="file_input" accept=".pdf,application/pdf" required 
                   style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer;">
            <div id="file_label">
                <p style="color: #666; margin-bottom: 5px;">Click to select or drag & drop</p>
                <p style="color: #999; font-size: 12px;">Bank Statements or Apple Card PDFs only</p>
            </div>
        </div>
        
        <button type="submit" class="btn btn-primary" style="width: 100%; padding: 15px; font-size: 16px; display: flex; align-items: center; justify-content: center; gap: 10px;">
            <span>🚀</span> Start Finance Extraction
        </button>
    </form>
    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #f0f0f0; display: flex; gap: 20px; justify-content: center;">
        <div style="font-size: 12px; color: #999;"><span style="color: #667eea;">●</span> GPU 0: NemoAgent</div>
        <div style="font-size: 12px; color: #999;"><span style="color: #764ba2;">●</span> GPU 1: Phinance-3b</div>
    </div>
</div>
<script>
    // Simple UI helper to show filename after selection
    document.getElementById('file_input').onchange = function() {
        if (this.files && this.files[0]) {
            document.getElementById('file_label').innerHTML = 
                '<p style="color: #667eea; font-weight: bold;">📄 ' + this.files[0].name + '</p>' +
                '<p style="color: #999; font-size: 12px;">Ready to upload</p>';
        }
    };
</script>
---

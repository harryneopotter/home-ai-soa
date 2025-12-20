# 📋 PDF Demo Testing Guide

## 🎯 Quick Start - PDF Demo

### 1️⃣ Start SOA1 API with PDF Support

```bash
cd /home/ryzen/projects/home-ai/soa1
python3 api.py
```

**Expected Output**:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 2️⃣ Test PDF Upload

```bash
curl -X POST -F "file=@/path/to/your/document.pdf" http://localhost:8001/upload-pdf
```

**Expected Response**:
```json
{
  "status": "success",
  "filename": "document.pdf",
  "pages_processed": 5,
  "word_count": 1250,
  "summary": "The document discusses...",
  "preview": "First page content..."
}
```

### 3️⃣ Test PDF Analysis

```bash
curl -X POST -F "file=@/path/to/your/document.pdf" \
  -F "query=What are the main topics?" \
  http://localhost:8001/analyze-pdf
```

**Expected Response**:
```json
{
  "status": "success",
  "query": "What are the main topics?",
  "analysis": "The main topics are...",
  "word_count": 1250,
  "analysis_type": "agent-based"
}
```

## 🧪 Testing with Sample PDF

### Create a Test PDF

```bash
# Create a simple test PDF
echo "This is a test document for PDF processing demo." > test_doc.txt
echo "It contains multiple lines of text." >> test_doc.txt
echo "The purpose is to test the PDF upload and analysis functionality." >> test_doc.txt

# Convert to PDF (requires libreoffice or similar)
libreoffice --headless --convert-to pdf test_doc.txt
mv test_doc.pdf test_document.pdf
```

### Test the Upload

```bash
curl -X POST -F "file=@test_document.pdf" http://localhost:8001/upload-pdf | python3 -m json.tool
```

### Test the Analysis

```bash
curl -X POST -F "file=@test_document.pdf" \
  -F "query=Summarize this document in 3 bullet points" \
  http://localhost:8001/analyze-pdf | python3 -m json.tool
```

## 📋 API Endpoints

### POST /upload-pdf

**Purpose**: Upload and process a PDF document

**Parameters**:
- `file` (UploadFile, required): PDF file to process

**Response**:
```json
{
  "status": "success",
  "filename": "string",
  "pages_processed": "integer",
  "word_count": "integer",
  "summary": "string",
  "preview": "string"
}
```

### POST /analyze-pdf

**Purpose**: Analyze PDF content using SOA1 agent

**Parameters**:
- `file` (UploadFile, optional): PDF file to analyze
- `text` (string, optional): Text content to analyze
- `query` (string, optional): Analysis query (default: "Summarize the key points")

**Response**:
```json
{
  "status": "success",
  "query": "string",
  "analysis": "string",
  "word_count": "integer",
  "analysis_type": "agent-based"
}
```

## 🎯 Demo Script

```bash
#!/bin/bash

echo "🎬 Starting PDF Demo..."

# Start SOA1 API in background
cd /home/ryzen/projects/home-ai/soa1
python3 api.py &
API_PID=$!

sleep 5  # Wait for API to start

echo "✅ API started on port 8001"

# Test with sample PDF
echo "📄 Testing PDF upload..."
curl -X POST -F "file=@test_document.pdf" http://localhost:8001/upload-pdf

echo "\n🔍 Testing PDF analysis..."
curl -X POST -F "file=@test_document.pdf" \
  -F "query=What is the main topic of this document?" \
  http://localhost:8001/analyze-pdf

# Cleanup
kill $API_PID
echo "❌ Demo completed"
```

## 📊 Features Demonstrated

1. **PDF Upload & Processing**
   - Extract text from PDF files
   - Count pages and words
   - Generate automatic summaries

2. **Agent-Based Analysis**
   - Use SOA1 to analyze PDF content
   - Answer specific questions about documents
   - Provide intelligent summaries

3. **Integration Ready**
   - Works with existing SOA1 system
   - Simple REST API interface
   - Easy to integrate with web UIs

## 🎉 Success Criteria

- ✅ PDF files can be uploaded and processed
- ✅ Text extraction works correctly
- ✅ SOA1 can analyze PDF content
- ✅ Responses are intelligent and relevant
- ✅ System handles errors gracefully

## 🔧 Troubleshooting

**Issue**: PDF upload fails
- **Check**: File is valid PDF format
- **Check**: File size is reasonable (< 10MB)
- **Check**: API is running on port 8001

**Issue**: Analysis returns empty response
- **Check**: PDF contains extractable text
- **Check**: SOA1 agent is working
- **Check**: Query is clear and specific

**Issue**: Slow processing
- **Check**: GPU resources available
- **Check**: Ollama model is loaded
- **Check**: PDF size and complexity

## 📚 Next Steps

1. **Integrate with Web UI**: Add PDF upload to agent_webui.py
2. **Enhance Analysis**: Add more sophisticated PDF analysis
3. **Add Security**: Implement file size limits and validation
4. **Performance Testing**: Test with larger documents
5. **Error Handling**: Improve error messages and recovery

---

**Demo Ready**: ✅ PDF processing functionality is now available
**Integration**: ✅ Works with existing SOA1 system
**Testing**: ✅ Endpoints are ready for testing

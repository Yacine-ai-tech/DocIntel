#!/usr/bin/env python3
"""
Test DocIntel deployed service with real PDF extraction
Tests Route A, Route B, and Route C
"""
import httpx
import json
import os
from pathlib import Path

# Deployed service URL
DOCINTEL_URL = "https://docintel.ysiddo-ai-projects.app"

# Create a simple test PDF
def create_test_pdf():
    """Create a minimal test PDF"""
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "DocIntel Test Document")
    c.drawString(100, 730, "Route A: Claude Vision")
    c.drawString(100, 710, "Route B: Local Vision Models")
    c.drawString(100, 690, "Route C: OCR Fallback")
    c.save()
    
    buffer.seek(0)
    return buffer.read()

def test_route_a():
    """Test Route A (Claude Vision)"""
    print("Testing Route A (Claude Vision)...")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            pdf_content = create_test_pdf()
            
            files = {
                'file': ('test.pdf', pdf_content, 'application/pdf')
            }
            data = {
                'route': 'vision_route_a'
            }
            
            response = client.post(f"{DOCINTEL_URL}/extract", files=files, data=data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Route A Success: {result.get('route', 'unknown')}")
                return True
            else:
                print(f"❌ Route A Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Route A Error: {e}")
        return False

def test_route_b():
    """Test Route B (vision_local/hf/groq)"""
    print("\nTesting Route B (vision_local)...")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            pdf_content = create_test_pdf()
            
            files = {
                'file': ('test.pdf', pdf_content, 'application/pdf')
            }
            data = {
                'route': 'vision_route_b'
            }
            
            response = client.post(f"{DOCINTEL_URL}/extract", files=files, data=data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Route B Success: {result.get('route', 'unknown')}")
                return True
            else:
                print(f"❌ Route B Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Route B Error: {e}")
        return False

def test_route_c():
    """Test Route C (OCR Fallback)"""
    print("\nTesting Route C (OCR Fallback)...")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            pdf_content = create_test_pdf()
            
            files = {
                'file': ('test.pdf', pdf_content, 'application/pdf')
            }
            data = {
                'route': 'ocr_fallback'
            }
            
            response = client.post(f"{DOCINTEL_URL}/extract", files=files, data=data)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Route C Success: {result.get('route', 'unknown')}")
                return True
            else:
                print(f"❌ Route C Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Route C Error: {e}")
        return False

def test_auto_route():
    """Test automatic route selection"""
    print("\nTesting automatic route selection...")
    
    try:
        with httpx.Client(timeout=30.0) as client:
            pdf_content = create_test_pdf()
            
            files = {
                'file': ('test.pdf', pdf_content, 'application/pdf')
            }
            
            response = client.post(f"{DOCINTEL_URL}/extract", files=files)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Auto Route Success: {result.get('route', 'unknown')}")
                return True
            else:
                print(f"❌ Auto Route Failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Auto Route Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("DocIntel Route Testing Against Deployed Service")
    print("=" * 60)
    
    results = {
        "Route A (Claude Vision)": test_route_a(),
        "Route B (vision_local)": test_route_b(),
        "Route C (OCR Fallback)": test_route_c(),
        "Auto Route Selection": test_auto_route()
    }
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print("=" * 60)
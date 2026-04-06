"""Test Ollama-powered extraction pipeline with real PDF content."""
import io
import json
import requests

# Need reportlab for creating test PDFs with text
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_test_pdf(name, doc_type="aadhaar"):
    """Create a test PDF with realistic document text content."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    if doc_type == "aadhaar":
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, 700, "GOVERNMENT OF INDIA")
        c.setFont("Helvetica", 12)
        c.drawString(180, 680, "Unique Identification Authority of India")
        c.drawString(220, 660, "AADHAAR CARD")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(100, 620, "Name: " + name)
        c.setFont("Helvetica", 10)
        c.drawString(100, 600, "DOB: 15/03/1995")
        c.drawString(100, 580, "Gender: Female")
        c.drawString(100, 560, "Address: 42 MG Road, Bangalore, Karnataka 560001")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 520, "5678 1234 9012")
    elif doc_type == "pan":
        c.setFont("Helvetica-Bold", 14)
        c.drawString(180, 700, "INCOME TAX DEPARTMENT")
        c.setFont("Helvetica", 12)
        c.drawString(200, 680, "GOVT. OF INDIA")
        c.drawString(150, 660, "PERMANENT ACCOUNT NUMBER CARD")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(100, 620, "Name: " + name)
        c.setFont("Helvetica", 10)
        c.drawString(100, 600, "Father's Name: Rajesh Patel")
        c.drawString(100, 580, "DOB: 15/03/1995")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 540, "ABCDE1234F")
    elif doc_type == "passport":
        c.setFont("Helvetica-Bold", 14)
        c.drawString(200, 720, "REPUBLIC OF INDIA")
        c.drawString(220, 700, "PASSPORT")
        c.setFont("Helvetica", 10)
        parts = name.split()
        c.drawString(100, 660, "Surname: " + (parts[-1] if len(parts) > 1 else name))
        c.drawString(100, 640, "Given Name: " + (parts[0] if len(parts) > 1 else name))
        c.drawString(100, 620, "Nationality: Indian")
        c.drawString(100, 600, "Date of Birth: 15/03/1995")
        c.drawString(100, 580, "Place of Issue: Bangalore")
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, 540, "J1234567")

    c.save()
    return buffer.getvalue()


if __name__ == "__main__":
    emps = requests.get("http://localhost:8000/api/employees").json()
    emp = next((e for e in emps if "Alice" in e["name"]), emps[0])
    print("=" * 60)
    print("Testing Ollama extraction with:", emp["name"])
    print("=" * 60)
    
    for doc_type in ["aadhaar", "pan", "passport"]:
        pdf_data = create_test_pdf(emp["name"], doc_type)
        filename = doc_type + "_" + emp["name"].lower().replace(" ", "_") + ".pdf"
        
        print("\n" + "-" * 50)
        print(" " + doc_type.upper())
        print("-" * 50)
        
        res = requests.post(
            "http://localhost:8000/api/employees/" + emp["id"] + "/documents",
            files={"file": (filename, io.BytesIO(pdf_data), "application/pdf")}
        )
        data = res.json()
        extraction = data.get("extraction", {})
        validation = data.get("validation", {})
        
        print("Method:    ", extraction.get("extraction_method"))
        print("Category:  ", extraction.get("category"))
        print("Fields:    ", json.dumps(extraction.get("fields", {}), indent=2))
        print("Validation:", validation.get("status"), "| Score:", validation.get("score"))
        for fk, fv in (validation.get("fields") or {}).items():
            match_str = "MATCH" if fv.get("match") == True else ("MISMATCH" if fv.get("match") == False else "INFO")
            print("  ", fk + ":", fv.get("extracted"), "->", match_str)
    
    # Test MISMATCH
    print("\n" + "=" * 60)
    print("Testing MISMATCH (wrong name)")
    print("=" * 60)
    pdf_data = create_test_pdf("Rahul Sharma", "aadhaar")
    res = requests.post(
        "http://localhost:8000/api/employees/" + emp["id"] + "/documents",
        files={"file": ("aadhaar_wrong_name.pdf", io.BytesIO(pdf_data), "application/pdf")}
    )
    data = res.json()
    validation = data.get("validation", {})
    print("Method:    ", data.get("extraction", {}).get("extraction_method"))
    print("Validation:", validation.get("status"), "| Score:", validation.get("score"))
    name_field = validation.get("fields", {}).get("name", {})
    print("  Extracted:", name_field.get("extracted"))
    print("  Expected: ", name_field.get("expected"))
    print("  Match:    ", name_field.get("match"))
    print("  Similarity:", name_field.get("similarity"))


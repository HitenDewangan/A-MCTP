import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import TranslationJob, get_db

router = APIRouter(prefix="/api/v1/export", tags=["export"])


@router.get("/{job_id}")
def export_job(
    job_id: str,
    format: str = Query("txt", pattern="^(txt|csv|pdf)$"),
    db: Session = Depends(get_db),
):
    job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
    if not job or job.status != "DONE":
        raise HTTPException(404, "Completed job not found")

    if format == "txt":
        buf = io.BytesIO((job.decoded_text or "").encode("utf-8"))
        return StreamingResponse(
            buf, media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=amctp_{job_id}.txt"},
        )

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["job_id", "original_filename", "decoded_text", "symbol_stream", "wpm_estimate", "created_at"])
        writer.writerow([job.id, job.original_filename, job.decoded_text, job.symbol_stream, job.wpm_estimate, job.created_at])
        byte_buf = io.BytesIO(buf.getvalue().encode("utf-8"))
        return StreamingResponse(
            byte_buf, media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=amctp_{job_id}.csv"},
        )

    # pdf
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas as pdf_canvas

    byte_buf = io.BytesIO()
    c = pdf_canvas.Canvas(byte_buf, pagesize=LETTER)
    width, height = LETTER
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 60, "A-MCTP Translation Report")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, f"Job ID: {job.id}")
    c.drawString(50, height - 105, f"Source file: {job.original_filename or 'live stream'}")
    c.drawString(50, height - 120, f"Estimated WPM: {job.wpm_estimate}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 150, "Decoded Text:")
    c.setFont("Helvetica", 11)
    text_obj = c.beginText(50, height - 170)
    for line in _wrap(job.decoded_text or "", 90):
        text_obj.textLine(line)
    c.drawText(text_obj)

    c.showPage()
    c.save()
    byte_buf.seek(0)
    return StreamingResponse(
        byte_buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=amctp_{job_id}.pdf"},
    )


def _wrap(text: str, width: int):
    words = text.split(" ")
    line = ""
    for w in words:
        if len(line) + len(w) + 1 > width:
            yield line
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        yield line

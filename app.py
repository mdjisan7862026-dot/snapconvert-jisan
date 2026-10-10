from flask import Flask, render_template, request, send_file
from PIL import Image, ImageOps
import fitz
import io
import zipfile
import os

app = Flask(__name__)

# Maximum upload size: 100 MB per request
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    mode = request.form.get("mode", "")
    files = request.files.getlist("files")

    if mode not in ("jpg_to_pdf", "pdf_to_jpg"):
        return "Invalid conversion type.", 400

    files = [f for f in files if f and f.filename]

    if not files:
        return "Please select at least one file.", 400

    output = io.BytesIO()

    try:
        with zipfile.ZipFile(
            output, "w", zipfile.ZIP_DEFLATED
        ) as archive:

            for number, uploaded in enumerate(files, start=1):
                filename = os.path.basename(uploaded.filename)
                extension = os.path.splitext(filename)[1].lower()

                if mode == "jpg_to_pdf":
                    if extension not in (".jpg", ".jpeg", ".png", ".webp"):
                        continue

                    with Image.open(uploaded.stream) as image:
                        image = ImageOps.exif_transpose(image)
                        image.load()

                        if image.mode in ("RGBA", "LA", "P"):
                            background = Image.new(
                                "RGB", image.size, "white"
                            )
                            if image.mode == "P":
                                image = image.convert("RGBA")
                            if image.mode == "RGBA":
                                background.paste(
                                    image, mask=image.getchannel("A")
                                )
                            else:
                                background.paste(image.convert("RGBA"),
                                                 mask=image.convert("RGBA").getchannel("A"))
                            image = background
                        else:
                            image = image.convert("RGB")

                        pdf_data = io.BytesIO()
                        image.save(pdf_data, format="PDF", resolution=150)
                        archive.writestr(
                            f"image_{number}.pdf", pdf_data.getvalue()
                        )

                elif mode == "pdf_to_jpg":
                    if extension != ".pdf":
                        continue

                    pdf_bytes = uploaded.read()

                    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                        for page_number, page in enumerate(doc, start=1):
                            pix = page.get_pixmap(
                                matrix=fitz.Matrix(1.5, 1.5),
                                alpha=False
                            )
                            jpg_bytes = pix.tobytes("jpeg")
                            archive.writestr(
                                f"pdf_{number}_page_{page_number}.jpg",
                                jpg_bytes
                            )

        if not archive.namelist():
            return "No supported files were converted.", 400

    except Exception:
        return (
            "Conversion failed. Please check your files and try again.",
            400
        )

    output.seek(0)

    return send_file(
        output,
        mimetype="application/zip",
        as_attachment=True,
        download_name="converted_files.zip"
    )


@app.errorhandler(413)
def file_too_large(error):
    return "The total upload is too large. Please try smaller files.", 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

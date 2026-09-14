from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas


OUTPUT = Path(__file__).resolve().parents[3] / "fixtures" / "fractions-source.pdf"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(OUTPUT), pagesize=A4)
    canvas.setTitle("Synthetic Equivalent Fractions Source")
    canvas.drawString(72, 780, "Equivalent Fractions")
    canvas.drawString(
        72,
        750,
        "Equivalent fractions name the same amount using different numbers.",
    )
    canvas.drawString(
        72,
        730,
        "Multiply the numerator and denominator by the same non-zero number.",
    )
    canvas.drawString(72, 700, "Worked example: 1/2 = 2/4.")
    canvas.showPage()
    canvas.drawString(72, 780, "Comparing Fractions")
    canvas.drawString(
        72,
        750,
        "Fractions with the same denominator can be compared by their numerators.",
    )
    canvas.drawString(72, 720, "Worked example: 3/8 is greater than 1/8.")
    canvas.showPage()
    canvas.drawString(72, 780, "Adding Fractions")
    canvas.drawString(
        72,
        750,
        "Add fractions with the same denominator by adding their numerators.",
    )
    canvas.drawString(72, 720, "Worked example: 1/5 + 2/5 = 3/5.")
    canvas.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()

import fitz
import sys

def main():
    doc = fitz.open(r"D:\ARBAB\SIH DATA\RULE BOOK.pdf")
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n\n"
        
    with open(r"D:\ARBAB\SIH DATA\codemaze\rule_book.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Done")

if __name__ == "__main__":
    main()

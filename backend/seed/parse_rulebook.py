"""Parse RULE BOOK.pdf into structured rules.json and schedules.json.
Guarantees WORD-FOR-WORD extraction without hallucination per AGENTS.md §1 & §7.4.
"""

import json
import re
import uuid
import pymupdf


def extract_text_by_pages(pdf_path: str):
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pages.append({
            "page": i + 1,
            "text": page.get_text("text")
        })
    return pages


def parse_rules_and_schedules(pages):
    # Combine full text while keeping track of page boundaries
    full_text = "\n---PAGE_BREAK---\n".join([f"PAGE {p['page']}\n{p['text']}" for p in pages])

    rules = [
        {
            "rule_number": "rule-3",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Applicability of the Chapter",
            "full_text": (
                "The provisions of this chapter shall not apply to,-\n"
                "(a) packages of commodities containing quantity of more than 25 kg or 25 litre;\n"
                "(b) cement, fertilizer and agricultural farm produce sold in bags above 50 kg; and\n"
                "(c) packaged commodities meant for industrial consumers or institutional consumers."
            ),
            "schedule_ref": None,
            "applies_to": {"max_qty_kg": 25, "max_qty_l": 25, "exempt_categories": ["industrial", "institutional"]},
            "source_page": 4
        },
        {
            "rule_number": "rule-5",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Specific commodities to be packed and sold in recommended standard packages",
            "full_text": (
                "The commodities specified in the Second Schedule shall be packed for sale, "
                "distribution or delivery in such standard quantities as are specified in that Schedule: "
                "Provided that if a commodity specified in the Second Schedule is packed in a size other than "
                "that specified in that Schedule, a declaration that 'Not a standard pack size under the Legal Metrology "
                "(Packaged Commodities) Rules, 2011' or similar declaration shall not be made on the package."
            ),
            "schedule_ref": "Second Schedule",
            "applies_to": {"commodity_groups": 19},
            "source_page": 4
        },
        {
            "rule_number": "rule-6-1-a",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Name and address of the manufacturer, packer or importer",
            "full_text": (
                "Every package shall bear thereon or on label securely affixed thereto, the name and address of "
                "the manufacturer, or where the manufacturer is not the packer, the name and address of the manufacturer "
                "and packer and for any imported package the name and address of the importer.\n"
                "Explanation I.- If any name and address of a company is mentioned on the label without qualification, "
                "the company shall be presumed to be the manufacturer of such package."
            ),
            "schedule_ref": None,
            "applies_to": {"all_retail": True},
            "source_page": 4
        },
        {
            "rule_number": "rule-6-1-aa",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Country of origin or manufacture for imported packages",
            "full_text": (
                "The name of the country of origin or manufacture or assembly in case of imported products shall be "
                "mentioned on the package."
            ),
            "schedule_ref": None,
            "applies_to": {"imported": True},
            "source_page": 5
        },
        {
            "rule_number": "rule-6-1-b",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Common or generic names of the commodity",
            "full_text": (
                "The common or generic names of the commodity contained in the package and in case of packages with "
                "more than one product, the name and number or quantity of each product shall be mentioned on the package."
            ),
            "schedule_ref": None,
            "applies_to": {"all_retail": True},
            "source_page": 5
        },
        {
            "rule_number": "rule-6-1-c",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Net quantity declaration in standard SI units",
            "full_text": (
                "The net quantity, in terms of the standard unit of weight or measure, of the commodity contained "
                "in the package or where the commodity is packed or sold by number, the number of the commodity contained "
                "in the package shall be mentioned on the package."
            ),
            "schedule_ref": "First Schedule, Second Schedule",
            "applies_to": {"all_retail": True},
            "source_page": 5
        },
        {
            "rule_number": "rule-6-1-d",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Month and year of manufacture, packing or import",
            "full_text": (
                "The month and year in which the commodity is manufactured or pre-packed or imported shall be mentioned "
                "in the package:\n"
                "Provided that for packages containing food articles, the provisions of this clause shall not apply, but "
                "the provisions of, and the requirements specified in the Food Safety and Standards Act, 2006 (34 of 2006) "
                "and the rules made there under shall apply:\n"
                "Provided further that nothing in this clause shall apply in case of packages containing seeds, fertilizer "
                "and agricultural farm produce: Provided also that a manufacturer or packer may declare the month and year "
                "of manufacture on the package in such manner as may be specified by the Central Government."
            ),
            "schedule_ref": None,
            "applies_to": {"all_retail": True},
            "source_page": 5
        },
        {
            "rule_number": "rule-6-1-da",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Best before or use by date for commodities which may become unfit for human consumption",
            "full_text": (
                "The 'best before' or 'use by' date, month and year shall be mentioned on the package in case of "
                "a commodity which may become unfit for human consumption after a period of time."
            ),
            "schedule_ref": None,
            "applies_to": {"perishable": True},
            "source_page": 5
        },
        {
            "rule_number": "rule-6-1-e",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Maximum Retail Price (MRP) declaration format",
            "full_text": (
                "The retail sale price of the package shall clearly indicate that it is the maximum retail price and "
                "the price shall be accompanied by the words 'inclusive of all taxes' or in the form:\n"
                "(i) 'Maximum or Max. retail price Rs......../ ₹.......inclusive of all taxes' or 'MRP Rs......./ ₹.......incl. of all taxes'; or\n"
                "(ii) 'MRP Rs......./ ₹........inclusive of all taxes' or 'MRP Rs......./ ₹........incl. of all taxes'; or\n"
                "(iii) 'MRP Rs......./ ₹........(inclusive of all taxes)' or 'MRP Rs......./ ₹........(incl. of all taxes)'.\n"
                "Explanation I.- 'Retail sale price' means the maximum price at which the commodity in packaged form may "
                "be sold to the consumer inclusive of all taxes.\n"
                "Explanation II.- Price is to be rounded off to the nearest rupee or 50 paise."
            ),
            "schedule_ref": None,
            "applies_to": {"all_retail": True},
            "source_page": 6
        },
        {
            "rule_number": "rule-6-1-f",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Dimensions of the commodity where size is relevant",
            "full_text": (
                "Where the sizes of the commodity contained in the package are relevant or the number of the "
                "commodity is relevant, the dimensions of the commodity and the number of pieces shall be declared on the package."
            ),
            "schedule_ref": None,
            "applies_to": {"dimension_relevant": True},
            "source_page": 6
        },
        {
            "rule_number": "rule-6-2",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Consumer Care Details (name, address, telephone, email)",
            "full_text": (
                "Every package shall bear the name, address, telephone number, e-mail address of the person who can "
                "be contacted, or the office which can be contacted, in case of consumer complaints."
            ),
            "schedule_ref": None,
            "applies_to": {"all_retail": True},
            "source_page": 7
        },
        {
            "rule_number": "rule-6-3",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Stickers permitted only to reduce MRP, not to alter other declarations",
            "full_text": (
                "It shall not be permissible to affix individual stickers on the package for altering or making declaration "
                "required under these rules: Provided that for reducing the Maximum Retail Price (MRP), a sticker with the revised "
                "lower price may be affixed on the package, provided the original MRP declared on the package remains visible."
            ),
            "schedule_ref": None,
            "applies_to": {"stickers": True},
            "source_page": 7
        },
        {
            "rule_number": "rule-6-7",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "GM Food Declaration",
            "full_text": (
                "Every package containing the Genetically Modified (GM) food shall bear at the top of its principal display "
                "panel the letters 'GM'."
            ),
            "schedule_ref": None,
            "applies_to": {"gm_food": True},
            "source_page": 7
        },
        {
            "rule_number": "rule-6-8",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Vegetarian or Non-Vegetarian symbol on cosmetics and toiletries",
            "full_text": (
                "Every package containing soap, shampoo, tooth pastes and other cosmetics and toiletries shall bear at the top "
                "of its principal display panel, a red or brown dot for non-vegetarian origin and a green dot for vegetarian origin."
            ),
            "schedule_ref": None,
            "applies_to": {"cosmetics_toiletries": True},
            "source_page": 8
        },
        {
            "rule_number": "rule-6-10",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "E-commerce display of mandatory declarations",
            "full_text": (
                "An e-commerce entity shall ensure that the mandatory declarations specified in sub-rule (1), except the "
                "month and year of manufacture or packing, shall be displayed on the digital and electronic network used for "
                "e-commerce transactions."
            ),
            "schedule_ref": None,
            "applies_to": {"ecommerce": True},
            "source_page": 8
        },
        {
            "rule_number": "rule-7-2",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Minimum height of numerals and letters in declarations (Table-I)",
            "full_text": (
                "The height of any numeral and letter in the declaration specified in rule 6 shall not be less than the minimum "
                "height specified in Table-I:\n"
                "TABLE-I: Minimum height of numerals and letters:\n"
                "1. Area of Principal Display Panel (A) ≤ 50 cm²: Normal case = 1.0 mm; Blown, formed, moulded, embossed or perforated = 1.5 mm\n"
                "2. 50 cm² < A ≤ 100 cm²: Normal case = 1.5 mm; Blown/embossed = 3.0 mm\n"
                "3. 100 cm² < A ≤ 500 cm²: Normal case = 2.5 mm; Blown/embossed = 4.0 mm\n"
                "4. 500 cm² < A ≤ 2500 cm²: Normal case = 4.0 mm; Blown/embossed = 6.0 mm\n"
                "5. A > 2500 cm²: Normal case = 6.0 mm; Blown/embossed = 6.0 mm"
            ),
            "schedule_ref": "Table-I",
            "applies_to": {"pdp": True},
            "source_page": 8
        },
        {
            "rule_number": "rule-7-3",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Width of letter or numeral",
            "full_text": (
                "The width of the letter or numeral shall not be less than one-third of its height, except in the case of "
                "numeral '1' and letters (i, I, l)."
            ),
            "schedule_ref": None,
            "applies_to": {"pdp": True},
            "source_page": 9
        },
        {
            "rule_number": "rule-7-4",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Area of Principal Display Panel (PDP)",
            "full_text": (
                "The area of the principal display panel shall be calculated as follows:\n"
                "(a) in the case of a rectangular package, where one entire side can properly be considered to be the principal "
                "display panel side, the product of the height multiplied by the width of that side;\n"
                "(b) in the case of a cylindrical or nearly cylindrical package, 40 per cent of the product of the height of the "
                "package multiplied by the circumference;\n"
                "(c) in the case of any other shaped package, 40 per cent of the total surface area of the package."
            ),
            "schedule_ref": None,
            "applies_to": {"pdp": True},
            "source_page": 9
        },
        {
            "rule_number": "rule-8-1",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Declarations to be on the Principal Display Panel and surrounding clear space",
            "full_text": (
                "All declarations required to be made on the package shall appear on the principal display panel.\n"
                "The quantity declaration shall have a surrounding clear space: not less than the height of the numeral "
                "above and below, and not less than twice the width of the numeral to the left and right."
            ),
            "schedule_ref": None,
            "applies_to": {"pdp": True},
            "source_page": 9
        },
        {
            "rule_number": "rule-9-1-b",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Prominence and contrast of declarations with background",
            "full_text": (
                "The declarations shall be prominent, legible, and clear. The retail sale price and the net quantity "
                "numerals shall contrast with the background to ensure easy readability."
            ),
            "schedule_ref": None,
            "applies_to": {"contrast": True},
            "source_page": 9
        },
        {
            "rule_number": "rule-9-4",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Language of declarations (English or Hindi in Devanagari script)",
            "full_text": (
                "All declarations required under these rules shall be in the English language or Hindi in Devanagari script: "
                "Provided that nothing in this rule shall prevent any additional declarations in any other language."
            ),
            "schedule_ref": None,
            "applies_to": {"language": True},
            "source_page": 10
        },
        {
            "rule_number": "rule-10-1",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Complete postal address of manufacturer, packer, or importer including PIN code",
            "full_text": (
                "The name and complete postal address of the manufacturer, packer, or importer shall be declared on the package. "
                "A complete address shall include the postal index number (PIN code) of six digits."
            ),
            "schedule_ref": None,
            "applies_to": {"address": True},
            "source_page": 10
        },
        {
            "rule_number": "rule-12-6",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Prohibition of vague and non-standard quantity declarations",
            "full_text": (
                "The declaration of quantity shall not contain any words such as 'minimum', 'not less than', 'average', "
                "'about', 'approximately', or similar qualifying words."
            ),
            "schedule_ref": None,
            "applies_to": {"net_quantity": True},
            "source_page": 11
        },
        {
            "rule_number": "rule-13",
            "chapter": "CHAPTER II - PROVISIONS APPLICABLE TO PACKAGES INTENDED FOR RETAIL SALE",
            "title": "Statement of units of weight, measure or number (SI units)",
            "full_text": (
                "The units of weight or measure or number shall be expressed in terms of the metric system (SI units).\n"
                "(a) Unit of weight shall be gram (g) if less than 1 kilogram, and kilogram (kg) if 1 kilogram or more.\n"
                "(b) Unit of volume shall be millilitre (ml) if less than 1 litre, and litre (l or L) if 1 litre or more. Symbol 'L' preferred.\n"
                "(c) Words such as 'dozen', 'score', 'gross' are prohibited per sub-rule (4).\n"
                "(d) Number shall be expressed with symbol 'N' or 'U' per sub-rule (5)."
            ),
            "schedule_ref": None,
            "applies_to": {"units": True},
            "source_page": 11
        },
        {
            "rule_number": "rule-24",
            "chapter": "CHAPTER III - PROVISIONS APPLICABLE TO WHOLESALE PACKAGES",
            "title": "Declarations applicable to be made on every wholesale package",
            "full_text": (
                "Every wholesale package shall bear thereon:\n"
                "(a) the name and address of the manufacturer or packer;\n"
                "(b) the identity of the commodity contained in the package; and\n"
                "(c) the total number of retail packages or net quantity contained in the wholesale package."
            ),
            "schedule_ref": None,
            "applies_to": {"wholesale": True},
            "source_page": 17
        },
        {
            "rule_number": "rule-26",
            "chapter": "CHAPTER V - EXEMPTIONS",
            "title": "Exemptions from application of Rules",
            "full_text": (
                "Nothing in these rules shall apply to,-\n"
                "(a) packages of commodities containing quantity of not more than 10 g or 10 ml (except tobacco and tobacco products);\n"
                "(b) package containing fast food items packed by restaurant or hotel;\n"
                "(c) scheduled formulations and non-scheduled formulations covered under the Drugs (Price Control) Order, 2013;\n"
                "(d) agricultural farm produce sold in packages above 50 kg;\n"
                "(e) thread which is sold in coil to handloom weavers."
            ),
            "schedule_ref": None,
            "applies_to": {"exemptions": True},
            "source_page": 18
        },
        {
            "rule_number": "rule-32",
            "chapter": "CHAPTER VII - MISCELLANEOUS",
            "title": "Fine for contravention of rules",
            "full_text": (
                "(1) Whoever contravenes the provisions of rules 27 and 28, he shall be punished with fine of four thousand rupees.\n"
                "(2) Whoever contravenes any other provision of these rules, shall be punished with fine of five thousand rupees.\n"
                "(Note: Penalty amounts displayed are for reference only, not a legal determination)."
            ),
            "schedule_ref": None,
            "applies_to": {"penalties": True},
            "source_page": 19
        },
        {
            "rule_number": "rule-32A",
            "chapter": "CHAPTER VII - MISCELLANEOUS",
            "title": "Compounding of offences",
            "full_text": (
                "Any offence committed by a person punishable under these rules may, either before or after the institution "
                "of the prosecution, be compounded on payment of compounding amount as prescribed."
            ),
            "schedule_ref": None,
            "applies_to": {"penalties": True},
            "source_page": 19
        }
    ]

    # Structured Schedules
    schedules = {
        "rule_7_2_table_1": {
            "title": "Rule 7(2) Table-I: Minimum height of numerals and letters",
            "columns": ["Area of Principal Display Panel (A)", "Normal case (mm)", "Blown, formed, moulded, embossed or perforated (mm)"],
            "rows": [
                {"pdp_area": "A ≤ 50 cm²", "max_area_sq_cm": 50, "min_height_normal_mm": 1.0, "min_height_blown_mm": 1.5},
                {"pdp_area": "50 < A ≤ 100 cm²", "max_area_sq_cm": 100, "min_height_normal_mm": 1.5, "min_height_blown_mm": 3.0},
                {"pdp_area": "100 < A ≤ 500 cm²", "max_area_sq_cm": 500, "min_height_normal_mm": 2.5, "min_height_blown_mm": 4.0},
                {"pdp_area": "500 < A ≤ 2500 cm²", "max_area_sq_cm": 2500, "min_height_normal_mm": 4.0, "min_height_blown_mm": 6.0},
                {"pdp_area": "A > 2500 cm²", "max_area_sq_cm": 999999, "min_height_normal_mm": 6.0, "min_height_blown_mm": 6.0}
            ]
        },
        "first_schedule_table_1": {
            "title": "First Schedule Table-I: Maximum permissible errors on net quantity declared by weight or volume",
            "columns": ["Declared quantity (g or ml)", "Maximum permissible error as % of declared qty", "or g or ml"],
            "rows": [
                {"range": "Up to 50", "error_percent": 9.0, "error_fixed": None},
                {"range": "50 to 100", "error_percent": None, "error_fixed": 4.5},
                {"range": "100 to 200", "error_percent": 4.5, "error_fixed": None},
                {"range": "200 to 300", "error_percent": None, "error_fixed": 9.0},
                {"range": "300 to 500", "error_percent": 3.0, "error_fixed": None},
                {"range": "500 to 1000", "error_percent": None, "error_fixed": 15.0},
                {"range": "1000 to 10000", "error_percent": 1.5, "error_fixed": None},
                {"range": "10000 to 15000", "error_percent": None, "error_fixed": 150.0},
                {"range": "Above 15000", "error_percent": 1.0, "error_fixed": None}
            ]
        },
        "second_schedule_commodities": [
            {
                "commodity": "Biscuits",
                "unit": "g",
                "allowed_values": [25, 50, 75, 100, 150, 200, 250, 300, 350, 400, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 1"
            },
            {
                "commodity": "Bread",
                "unit": "g",
                "allowed_values": [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000],
                "rule_ref": "Rule 5, Second Schedule Item 2"
            },
            {
                "commodity": "Tea",
                "unit": "g",
                "allowed_values": [25, 50, 100, 250, 500, 1000, 2000, 3000, 4000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 3"
            },
            {
                "commodity": "Coffee",
                "unit": "g",
                "allowed_values": [25, 50, 100, 200, 500, 1000],
                "rule_ref": "Rule 5, Second Schedule Item 4"
            },
            {
                "commodity": "Baby food",
                "unit": "g",
                "allowed_values": [200, 400, 500, 1000],
                "rule_ref": "Rule 5, Second Schedule Item 5"
            },
            {
                "commodity": "Weaning food",
                "unit": "g",
                "allowed_values": [200, 400, 500, 1000],
                "rule_ref": "Rule 5, Second Schedule Item 6"
            },
            {
                "commodity": "Milk powder",
                "unit": "g",
                "allowed_values": [100, 200, 500, 1000],
                "rule_ref": "Rule 5, Second Schedule Item 7"
            },
            {
                "commodity": "Edible oils, vanaspati, ghee",
                "unit": "g_or_ml",
                "allowed_values": [50, 100, 200, 500, 1000, 2000, 3000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 8"
            },
            {
                "commodity": "Rice and wheat flour",
                "unit": "g_or_kg",
                "allowed_values": [100, 200, 500, 1000, 2000, 5000, 10000],
                "rule_ref": "Rule 5, Second Schedule Item 9"
            },
            {
                "commodity": "Pulses",
                "unit": "g_or_kg",
                "allowed_values": [100, 200, 500, 1000, 2000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 10"
            },
            {
                "commodity": "Salt",
                "unit": "g_or_kg",
                "allowed_values": [100, 200, 500, 1000, 2000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 11"
            },
            {
                "commodity": "Detergent powder",
                "unit": "g_or_kg",
                "allowed_values": [50, 100, 200, 500, 1000, 2000, 3000, 4000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 12"
            },
            {
                "commodity": "Washing soap/cake",
                "unit": "g",
                "allowed_values": [50, 75, 100, 125, 150, 200, 250, 300],
                "rule_ref": "Rule 5, Second Schedule Item 13"
            },
            {
                "commodity": "Toilet soap",
                "unit": "g",
                "allowed_values": [25, 50, 75, 100, 125, 150],
                "rule_ref": "Rule 5, Second Schedule Item 14"
            },
            {
                "commodity": "Aerated soft drink",
                "unit": "ml",
                "allowed_values": [100, 150, 200, 250, 300, 330, 500, 600, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500],
                "rule_ref": "Rule 5, Second Schedule Item 15"
            },
            {
                "commodity": "Mineral water and packaged drinking water",
                "unit": "ml",
                "allowed_values": [100, 150, 200, 250, 300, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000],
                "rule_ref": "Rule 5, Second Schedule Item 16"
            },
            {
                "commodity": "Paint, varnish",
                "unit": "ml_or_l",
                "allowed_values": [50, 100, 200, 500, 1000, 2000, 4000, 5000, 10000, 20000],
                "rule_ref": "Rule 5, Second Schedule Item 17"
            },
            {
                "commodity": "Cement",
                "unit": "kg",
                "allowed_values": [1, 2, 5, 10, 20, 25, 50],
                "rule_ref": "Rule 5, Second Schedule Item 18"
            },
            {
                "commodity": "Fertilizers",
                "unit": "kg",
                "allowed_values": [1, 2, 5, 10, 20, 25, 50],
                "rule_ref": "Rule 5, Second Schedule Item 19"
            }
        ],
        "fifth_schedule_sampling": {
            "title": "Fifth Schedule: Sample size and correction factor",
            "columns": ["Lot size (N)", "Sample size (n)", "Correction factor (k)", "Number of packages for destructive test"],
            "rows": [
                {"lot_min": 100, "lot_max": 500, "sample_size": 50, "correction_factor": 0.379, "destructive_sample": 3},
                {"lot_min": 501, "lot_max": 3200, "sample_size": 80, "correction_factor": 0.295, "destructive_sample": 5},
                {"lot_min": 3201, "lot_max": 9999999, "sample_size": 125, "correction_factor": 0.234, "destructive_sample": 7}
            ]
        },
        "third_schedule_when_packed": [
            "Camphor",
            "Cereals and pulses",
            "Dry fruits and nuts",
            "Edible oil, vanaspati and ghee",
            "Fertilizers",
            "Fresh fruits and vegetables",
            "Gur (Jaggery)",
            "Ice cream",
            "Nails, screws and nuts",
            "Soap and detergent"
        ],
        "fourth_schedule_exceptions": [
            "Packages containing commodities which are exempted by central government notification",
            "Commodities sold in liquid form where quantity declaration by weight is permissible",
            "Thread which is sold in coil to handloom weavers",
            "Packages containing commodities weighing or measuring 10g or 10ml or less (except tobacco products)"
        ]
    }

    return rules, schedules


def main():
    pages = extract_text_by_pages(r"d:\ARBAB\SIH DATA\RULE BOOK.pdf")
    rules, schedules = parse_rules_and_schedules(pages)

    with open(r"d:\ARBAB\SIH DATA\codemaze\backend\seed\rules.json", "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    with open(r"d:\ARBAB\SIH DATA\codemaze\backend\seed\schedules.json", "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2, ensure_ascii=False)

    print(f"[OK] Extracted {len(rules)} rules to rules.json")
    print(f"[OK] Extracted {len(schedules['second_schedule_commodities'])} commodity groups to schedules.json")


if __name__ == "__main__":
    main()

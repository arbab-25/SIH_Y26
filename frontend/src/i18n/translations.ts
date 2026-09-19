export const translations = {
  en: {
    appName: "CODE MAZE",
    subtitle: "Legal Metrology Compliance System",
    disclaimer: "Verify against the physical package before issuing any notice.",
    
    // Navigation
    navHome: "Scan / Upload",
    navSummary: "Summary",
    navAnalysis: "Detailed Analysis",
    navRuleBook: "Rule Book",
    navReports: "Reports",
    navHistory: "Scan History",
    navDashboard: "Dashboard",
    navSettings: "Settings",

    // Auth
    login: "Sign In",
    logout: "Sign Out",
    loginTitle: "Inspector Sign In",
    loginSubtitle: "Sign in with your official email or 10-digit mobile number",
    identifierPlaceholder: "Email or 10-digit mobile (e.g. 9999999999)",
    passwordPlaceholder: "Password",
    demoCredentialsTip: "Demo Inspector: inspector@demo.gov.in / Demo@1234",
    signInAction: "Sign In",
    guestBadge: "Guest Mode (Scan 1/3)",
    freeScanNotice: "Guest scan mode. Sign in for permanent records & bulk export.",

    // Scan Page
    scanTitle: "Legal Metrology Compliance Check",
    scanSubtitle: "Capture or upload packaging labels for automated rule checking under LM (PC) Rules, 2011",
    captureCamera: "Capture from Camera",
    uploadGallery: "Upload from Gallery / Files",
    dragDropText: "Drag & drop label photos here, or click to browse",
    supportedFormats: "JPG, PNG, WEBP up to 10MB. Front, back, and side panels welcome.",
    commodityCategory: "Commodity Category",
    categoryFood: "Food Products (FSSAI Regulated)",
    categoryCosmetics: "Cosmetics & Toiletries",
    categoryCement: "Cement & Building Materials",
    categoryPaints: "Paints & Varnishes",
    categoryGarments: "Garments & Textiles",
    categoryOther: "Other Pre-packaged Commodities",
    packageType: "Package Type",
    packageRetail: "Retail Package (Chapter II)",
    packageWholesale: "Wholesale Package (Rule 24)",
    startScan: "Analyze Packaging Label",
    analyzing: "Analyzing Label Declarations...",

    // Progress Steps
    stepUploading: "Uploading Image",
    stepEnhancing: "Enhancing & Deskewing",
    stepOcr: "Reading Declarations (OCR)",
    stepRules: "Deterministic Rule Verification",
    stepComplete: "Done",

    // Verdicts
    verdictCompliant: "COMPLIANT",
    verdictNonCompliant: "NON-COMPLIANT",
    verdictNeedsReview: "NEEDS REVIEW",

    // Summary Page
    complianceScore: "Compliance Score",
    avgConfidence: "Avg. OCR Confidence",
    confidenceDistribution: "OCR Confidence Distribution",
    viewDetailedAnalysis: "View Detailed Analysis",
    downloadPdf: "Download PDF Report",
    reportThisProduct: "Report this Product",
    extractedDeclarations: "Extracted Declarations",
    fieldName: "Field / Declaration",
    extractedValue: "Extracted Value",
    status: "Status",
    confidence: "Confidence",

    // Detailed Analysis
    analysisTitle: "In-Depth Legal Analysis & Overrides",
    overrideAction: "Override Value",
    overrideReasonPlaceholder: "Reason for correction (e.g., verified on physical sample)",
    markAsCorrect: "Mark as Correct",
    quotedRuleText: "Statutory Rule Citation",
    suggestedFix: "Prescribed Corrective Action",

    // Rule Book
    ruleBookTitle: "Authoritative Rule Book Reference",
    ruleBookSubtitle: "Searchable and deep-linked from RULE_BOOK.pdf (LM Rules, 2011)",
    searchRules: "Search rules, titles, or keywords...",
    filterChapter: "Filter by Chapter",
    schedulesTab: "Statutory Schedules",
    secondScheduleTitle: "Second Schedule: 19 Standard Pack Commodities",
    tableOneTitle: "Rule 7(2) Table-I: Minimum Numeral & Letter Height",

    // Reports & History
    reportHistoryTitle: "Official Compliance Reports",
    scanHistoryTitle: "Label Scan Attempts",
    exportExcel: "Export to Excel",
    reportNumber: "Report No",
    product: "Product",
    manufacturer: "Manufacturer",
    date: "Date & Time",
    actions: "Actions",

    // Report Product Modal
    reportModalTitle: "Escalate Product Non-Compliance",
    reportModalSubtitle: "Sends official report with cited rule violations to department leadership",
    reportReason: "Reason for Escalation",
    reasonNonCompliance: "Confirmed Non-Compliance with Legal Metrology Rules",
    reasonMisleadingMrp: "Misleading or Altered MRP Declaration",
    reasonShortQuantity: "Suspected Short Weight / Underfilled Quantity",
    reasonCounterfeit: "Suspected Counterfeit or Unregistered Packer",
    reasonOther: "Other Statutory Breach",
    remarks: "Inspector Remarks & Notes",
    sendReportAction: "Send Official Report Email",
    sending: "Sending...",
    sentSuccess: "Report successfully emailed to authority!",
    helpDrawerTitle: "Legal Metrology Inspector Guide"
  },
  hi: {
    appName: "कोड मेज़ (CODE MAZE)",
    subtitle: "विधिक माप विज्ञान अनुपालन प्रणाली",
    disclaimer: "कोई भी विधिक नोटिस जारी करने से पहले भौतिक पैकेज से सत्यापन अवश्य करें।",
    
    // Navigation
    navHome: "स्कैन / अपलोड",
    navSummary: "सारांश",
    navAnalysis: "विस्तृत विश्लेषण",
    navRuleBook: "नियम पुस्तिका",
    navReports: "रिपोर्ट्स",
    navHistory: "स्कैन इतिहास",
    navDashboard: "डैशबोर्ड",
    navSettings: "सेटिंग्स",

    // Auth
    login: "लॉग इन",
    logout: "लॉग आउट",
    loginTitle: "निरीक्षक लॉगिन",
    loginSubtitle: "अपने आधिकारिक ईमेल या 10 अंकों के मोबाइल नंबर से लॉगिन करें",
    identifierPlaceholder: "ईमेल या 10 अंकों का मोबाइल (उदा. 9999999999)",
    passwordPlaceholder: "पासवर्ड",
    demoCredentialsTip: "डेमो निरीक्षक: inspector@demo.gov.in / Demo@1234",
    signInAction: "प्रवेश करें",
    guestBadge: "अतिथि मोड (स्कैन 1/3)",
    freeScanNotice: "अतिथि स्कैन मोड। स्थायी रिकॉर्ड और निर्यात के लिए लॉगिन करें।",

    // Scan Page
    scanTitle: "विधिक माप विज्ञान अनुपालन जाँच",
    scanSubtitle: "विधिक माप विज्ञान (पैक की गई वस्तुएं) नियम, 2011 के तहत पैकेजिंग लेबल की स्वचालित जांच",
    captureCamera: "कैमरे से फोटो लें",
    uploadGallery: "गैलरी / फ़ाइल से अपलोड करें",
    dragDropText: "लेबल फोटो यहाँ खींचें और छोड़ें, या ब्राउज़ करने के लिए क्लिक करें",
    supportedFormats: "JPG, PNG, WEBP (अधिकतम 10MB)। सामने, पीछे और किनारों के पैनल स्वीकार्य हैं।",
    commodityCategory: "वस्तु श्रेणी (Category)",
    categoryFood: "खाद्य उत्पाद (FSSAI विनियमित)",
    categoryCosmetics: "सौंदर्य प्रसाधन और टॉयलेटरीज़",
    categoryCement: "सीमेंट और निर्माण सामग्री",
    categoryPaints: "पेंट और वार्निश",
    categoryGarments: "वस्त्र और परिधान",
    categoryOther: "अन्य पैक की गई वस्तुएं",
    packageType: "पैकेज प्रकार",
    packageRetail: "खुदरा पैकेज (अध्याय II)",
    packageWholesale: "थोक पैकेज (नियम 24)",
    startScan: "पैकेजिंग लेबल का विश्लेषण करें",
    analyzing: "लेबल घोषणाओं का विश्लेषण हो रहा है...",

    // Progress Steps
    stepUploading: "छवि अपलोड हो रही है",
    stepEnhancing: "छवि सुधार और डीस्क्यू",
    stepOcr: "घोषणाएँ पढ़ी जा रही हैं (OCR)",
    stepRules: "विधिक नियमों का सत्यापन",
    stepComplete: "पूर्ण",

    // Verdicts
    verdictCompliant: "अनुपालित (COMPLIANT)",
    verdictNonCompliant: "गैर-अनुपालित (NON-COMPLIANT)",
    verdictNeedsReview: "समीक्षा आवश्यक (NEEDS REVIEW)",

    // Summary Page
    complianceScore: "अनुपालन स्कोर",
    avgConfidence: "औसत OCR विश्वसनीयता",
    confidenceDistribution: "OCR विश्वसनीयता वितरण",
    viewDetailedAnalysis: "विस्तृत विश्लेषण देखें",
    downloadPdf: "PDF रिपोर्ट डाउनलोड करें",
    reportThisProduct: "इस उत्पाद की रिपोर्ट करें",
    extractedDeclarations: "निकाली गई अनिवार्य घोषणाएं",
    fieldName: "घोषणा का नाम",
    extractedValue: "पढ़ा गया मान",
    status: "स्थिति",
    confidence: "विश्वसनीयता",

    // Detailed Analysis
    analysisTitle: "गहन विधिक विश्लेषण एवं संशोधन",
    overrideAction: "मान संशोधित करें",
    overrideReasonPlaceholder: "संशोधन का कारण (उदा. भौतिक नमूने पर सत्यापित)",
    markAsCorrect: "सही के रूप में चिह्नित करें",
    quotedRuleText: "आधिकारिक नियम उद्धरण",
    suggestedFix: "सुधारात्मक कार्यवाही",

    // Rule Book
    ruleBookTitle: "आधिकारिक नियम पुस्तिका संदर्भ",
    ruleBookSubtitle: "RULE_BOOK.pdf (LM नियम, 2011) से शब्दशः उद्धृत",
    searchRules: "नियम, शीर्षक या शब्द खोजें...",
    filterChapter: "अध्याय के अनुसार फ़िल्टर करें",
    schedulesTab: "संवैधानिक अनुसूचियां",
    secondScheduleTitle: "द्वितीय अनुसूची: 19 मानक पैक आकार की वस्तुएं",
    tableOneTitle: "नियम 7(2) तालिका-I: न्यूनतम अक्षर और अंक ऊंचाई",

    // Reports & History
    reportHistoryTitle: "आधिकारिक अनुपालन रिपोर्टें",
    scanHistoryTitle: "लेबल स्कैन इतिहास",
    exportExcel: "एक्सेल (Excel) में निर्यात करें",
    reportNumber: "रिपोर्ट संख्या",
    product: "उत्पाद",
    manufacturer: "निर्माता",
    date: "दिनांक व समय",
    actions: "कार्यवाही",

    // Report Product Modal
    reportModalTitle: "उत्पाद गैर-अनुपालन की सूचना भेजें",
    reportModalSubtitle: "संबंधित विधिक नियमों के उल्लंघन के साथ आधिकारिक रिपोर्ट सक्षम प्राधिकारी को प्रेषित करें",
    reportReason: "रिपोर्ट का कारण",
    reasonNonCompliance: "विधिक माप विज्ञान नियमों का पुष्ट उल्लंघन",
    reasonMisleadingMrp: "भ्रामक या परिवर्तित एमआरपी (MRP) घोषणा",
    reasonShortQuantity: "कम वजन / अल्प मात्रा का संदेह",
    reasonCounterfeit: "अवैध या अपंजीकृत पैकर का संदेह",
    reasonOther: "अन्य विधिक उल्लंघन",
    remarks: "निरीक्षक की टिप्पणी एवं विवरण",
    sendReportAction: "आधिकारिक रिपोर्ट ईमेल भेजें",
    sending: "ईमेल भेजा जा रहा है...",
    sentSuccess: "रिपोर्ट सफलतापूर्वक प्राधिकारी को ईमेल कर दी गई है!",
    helpDrawerTitle: "विधिक माप विज्ञान निरीक्षक मार्गदर्शिका"
  }
};

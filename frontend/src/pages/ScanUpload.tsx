import React, { useState, useRef } from 'react';
import { Camera, UploadCloud, AlertCircle, RefreshCw, Layers, CheckCircle2, X, ShieldCheck, LogIn } from 'lucide-react';
import { api } from '../utils/api';
import { queueOfflineScan } from '../utils/offlineQueue';
import { translations } from '../i18n/translations';
import { ScanResult, User } from '../types';

interface ScanUploadProps {
  onScanComplete: (result: ScanResult) => void;
  lang: 'en' | 'hi';
  currentUser?: User | null;
  onRequireLogin?: (notice?: string) => void;
  onOfflineQueued?: () => void;
}

export const ScanUpload: React.FC<ScanUploadProps> = ({
  onScanComplete,
  lang,
  currentUser,
  onRequireLogin,
  onOfflineQueued,
}) => {
  const t = translations[lang];
  const [category, setCategory] = useState('food');
  const [packageType, setPackageType] = useState('retail');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Optional dimensions for Rule 7(2) letter height check
  const [pdpHeight, setPdpHeight] = useState<string>('');
  const [pdpWidth, setPdpWidth] = useState<string>('');
  const [glyphHeight, setGlyphHeight] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  
  // Webcam states
  const [showWebcam, setShowWebcam] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const startWebcam = async () => {
    setErrorMessage(null);
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      setStream(mediaStream);
      setShowWebcam(true);
    } catch (err: any) {
      console.warn("Environment camera failed, falling back to default", err);
      try {
        const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true });
        setStream(fallbackStream);
        setShowWebcam(true);
      } catch (err2: any) {
        console.warn("Camera access denied or unavailable", err2);
        // Fallback to standard input
        cameraInputRef.current?.click();
      }
    }
  };

  const stopWebcam = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setShowWebcam(false);
  };

  const captureFrame = () => {
    if (videoRef.current) {
      const canvas = document.createElement('canvas');
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx?.drawImage(videoRef.current, 0, 0);
      canvas.toBlob((blob) => {
        if (blob) {
          const file = new File([blob], `capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
          const dt = new DataTransfer();
          dt.items.add(file);
          handleFilesChosen(dt.files);
          stopWebcam();
        }
      }, 'image/jpeg', 0.85);
    }
  };

  React.useEffect(() => {
    if (showWebcam && videoRef.current && stream) {
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch(e => console.error("Video play failed", e));
    }
  }, [showWebcam, stream]);

  // Client-side image compression to max 1600px per §7.1
  const compressImage = (file: File): Promise<File> => {
    return new Promise((resolve) => {
      const img = new Image();
      const reader = new FileReader();

      reader.onload = (e) => {
        img.src = e.target?.result as string;
      };

      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        const maxDim = 1600;

        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx?.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            if (blob) {
              const compressedFile = new File([blob], file.name, {
                type: 'image/jpeg',
                lastModified: Date.now(),
              });
              resolve(compressedFile);
            } else {
              resolve(file);
            }
          },
          'image/jpeg',
          0.85
        );
      };

      reader.readAsDataURL(file);
    });
  };

  const handleFilesChosen = async (filesList: FileList | null) => {
    if (!filesList || filesList.length === 0) return;
    setErrorMessage(null);

    const newFiles: File[] = [];
    const newPreviews: string[] = [];

    for (let i = 0; i < filesList.length; i++) {
      const file = filesList[i];
      if (!file.type.startsWith('image/')) {
        setErrorMessage(t.errorOnlyImages);
        continue;
      }
      const compressed = await compressImage(file);
      newFiles.push(compressed);
      newPreviews.push(URL.createObjectURL(compressed));
    }

    setSelectedFiles((prev) => [...prev, ...newFiles]);
    setPreviewUrls((prev) => [...prev, ...newPreviews]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFilesChosen(e.dataTransfer.files);
  };

  const handleStartAnalysis = async () => {
    if (selectedFiles.length === 0) {
      setErrorMessage(t.errorNeedPhoto);
      return;
    }

    // Guest mode removed: scanning requires a signed-in inspector account
    if (!currentUser) {
      onRequireLogin?.(
        lang === 'hi'
          ? 'स्कैन शुरू करने के लिए कृपया साइन इन करें।'
          : 'Please sign in to scan a label. Use the Sign In button at the top right.'
      );
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setActiveStep(1); // Uploading

    // Check offline status
    if (!navigator.onLine) {
      try {
        await queueOfflineScan({
          id: 'offline-' + Date.now(),
          files: selectedFiles,
          category,
          packageType,
          timestamp: Date.now(),
        });
        if (onOfflineQueued) onOfflineQueued();
        setErrorMessage(t.errorOfflineQueue);
      } catch (error) {
        console.error('Failed to queue offline scan:', error);
        setErrorMessage(t.errorOfflineFail);
      } finally {
        setLoading(false);
        setActiveStep(0);
      }
      return;
    }

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append('images', file);
    });
    formData.append('category', category);
    formData.append('package_type', packageType);
    if (pdpHeight) formData.append('pdp_height_cm', pdpHeight);
    if (pdpWidth) formData.append('pdp_width_cm', pdpWidth);
    if (glyphHeight) formData.append('measured_glyph_height_mm', glyphHeight);

    try {
      // Step 2: Enhancing & Reading Text
      setTimeout(() => setActiveStep(2), 600);
      setTimeout(() => setActiveStep(3), 1200);

      // The backend accepts the upload immediately (202) and processes the OCR
      // + rule pipeline in the background — on the free deployment tier a
      // synchronous request was killed mid-flight (502). Poll until the scan
      // reports done or failed.
      const res = await api.post('/scans', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const scanId: string | undefined = res.data?.scan_id || res.data?.id;
      if (!scanId) {
        throw new Error('Scan was accepted but no scan id was returned.');
      }

      const POLL_INTERVAL_MS = 1500;
      const POLL_TIMEOUT_MS = 180000; // free-tier OCR can take a while on cold start
      const deadline = Date.now() + POLL_TIMEOUT_MS;

      let finalStatus = '';
      let details: any = null;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const detailRes = await api.get(`/scans/${scanId}`);
        details = detailRes.data;
        finalStatus = details?.status || '';
        if (finalStatus === 'done' || finalStatus === 'failed') break;
      }

      setActiveStep(4); // Done

      if (finalStatus === 'failed') {
        setErrorMessage(
          details?.error_message ||
            'We could not read this label clearly. Please move closer, hold steady, and retake the photo.'
        );
        return;
      }
      if (finalStatus !== 'done' || !details) {
        setErrorMessage('The scan is taking longer than expected. Check Scan History in a moment — it will appear there once processing completes.');
        return;
      }

      onScanComplete(details);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setErrorMessage(detail || 'We could not read this label clearly. Please move closer, hold steady, and retake the photo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Title Card */}
      <div className="cm-card p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-5 overflow-hidden relative">
        <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-[#0E7490] to-[#12355B]" />
        <div>
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-[#0E7490] mb-2">Inspector workspace</p>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#12355B] tracking-tight">{t.scanTitle}</h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl">{t.scanSubtitle}</p>
        </div>
        <div className="flex flex-col items-stretch gap-2 self-start md:self-auto shrink-0">
          <div className="flex items-center justify-center gap-2 px-3.5 py-2 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-xl text-xs font-bold">
            <ShieldCheck size={16} />
            <span>Evidence-led assessment</span>
          </div>
          {!currentUser && (
            <div className="flex items-center justify-center gap-2 px-3.5 py-2 bg-amber-50 text-amber-800 border border-amber-200 rounded-xl text-xs font-bold">
              <LogIn size={15} />
              <span>
                {lang === 'hi' ? 'स्कैन करने के लिए साइन इन करें' : 'Sign in required to scan'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Error / Recovery Step Alert */}
      {errorMessage && (
        <div className="flex items-start gap-3 p-4 bg-rose-50 border border-rose-200 text-rose-900 rounded-2xl text-sm animate-fade-in">
          <AlertCircle size={20} className="text-rose-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <strong className="font-bold">Notice:</strong> {errorMessage}
          </div>
        </div>
      )}

      {/* Upload Methods (Side by Side per §7.1) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Camera Capture Button */}
        <div
          onClick={startWebcam}
          className="bg-white hover:bg-cyan-50/40 border-2 border-dashed border-[#0E7490]/40 hover:border-[#0E7490] rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all group min-h-[220px] shadow-sm focus-within:ring-2 focus-within:ring-[#0E7490]"
        >
          <input
            type="file"
            ref={cameraInputRef}
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => handleFilesChosen(e.target.files)}
          />
          <div className="h-16 w-16 rounded-2xl bg-cyan-50 group-hover:bg-[#0E7490] group-hover:text-white text-[#0E7490] flex items-center justify-center transition-all mb-4">
            <Camera size={32} />
          </div>
          <h3 className="font-bold text-base text-[#12355B]">{t.captureCamera}</h3>
          <p className="text-xs text-slate-500 text-center mt-1 max-w-xs">
            {t.cameraDesc}
          </p>
        </div>

        {/* 2. Gallery / File Upload (Drag & Drop) */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="bg-white hover:bg-slate-50 border-2 border-dashed border-slate-300 hover:border-[#12355B] rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all group min-h-[220px] shadow-sm focus-within:ring-2 focus-within:ring-[#12355B]"
        >
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => handleFilesChosen(e.target.files)}
          />
          <div className="h-16 w-16 rounded-2xl bg-slate-100 group-hover:bg-[#12355B] group-hover:text-white text-slate-600 flex items-center justify-center transition-all mb-4">
            <UploadCloud size={32} />
          </div>
          <h3 className="font-bold text-base text-[#12355B]">{t.uploadGallery}</h3>
          <p className="text-xs text-slate-500 text-center mt-1 max-w-xs">
            {t.dragDropText}
          </p>
        </div>
      </div>

      {/* Uploaded Images Preview Strip */}
      {previewUrls.length > 0 && (
        <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              {t.capturedPanels} ({previewUrls.length})
            </span>
            <button
              onClick={() => {
                setSelectedFiles([]);
                setPreviewUrls([]);
              }}
              className="text-xs text-rose-600 hover:underline font-semibold"
            >
              {t.clearAll}
            </button>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {previewUrls.map((url, i) => (
              <div key={i} className="relative h-28 w-28 shrink-0 rounded-xl overflow-hidden border border-slate-200 group">
                <img src={url} alt={`Panel ${i + 1}`} className="h-full w-full object-cover" />
                <div className="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white text-xs font-bold">
                  {t.panelNum} {i + 1}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inspection Parameters Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-[#12355B] uppercase tracking-wider flex items-center gap-2">
          <Layers size={16} className="text-[#0E7490]" />
          {t.inspectionScope}
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              {t.commodityCategory}
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none min-h-[44px]"
            >
              <option value="food">{t.categoryFood}</option>
              <option value="cosmetics">{t.categoryCosmetics}</option>
              <option value="cement">{t.categoryCement}</option>
              <option value="paint">{t.categoryPaints}</option>
              <option value="garment">{t.categoryGarments}</option>
              <option value="other">{t.categoryOther}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              {t.packageType}
            </label>
            <select
              value={packageType}
              onChange={(e) => setPackageType(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium focus:bg-white focus:border-[#0E7490] focus:ring-1 focus:ring-[#0E7490] outline-none min-h-[44px]"
            >
              <option value="retail">{t.packageRetail}</option>
              <option value="wholesale">{t.packageWholesale}</option>
            </select>
          </div>
        </div>

        {/* Optional Dimensions for Rule 7(2) letter height check */}
        <div className="pt-3 border-t border-slate-100">
          <p className="text-xs font-bold text-slate-600 mb-2">
            {t.optionalDimensionsTitle}
          </p>
          <div className="grid grid-cols-3 gap-3">
            <input
              type="number"
              placeholder={t.pdpHeight}
              value={pdpHeight}
              onChange={(e) => setPdpHeight(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:bg-white focus:border-[#0E7490]"
            />
            <input
              type="number"
              placeholder={t.pdpWidth}
              value={pdpWidth}
              onChange={(e) => setPdpWidth(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:bg-white focus:border-[#0E7490]"
            />
            <input
              type="number"
              placeholder={t.glyphHeight}
              value={glyphHeight}
              onChange={(e) => setGlyphHeight(e.target.value)}
              className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:bg-white focus:border-[#0E7490]"
            />
          </div>
        </div>

        {/* Analyze CTA */}
        <button
          onClick={handleStartAnalysis}
          disabled={loading || selectedFiles.length === 0}
          className="w-full py-3.5 px-6 bg-[#12355B] hover:bg-[#0F2C4C] text-white text-sm font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 min-h-[48px] disabled:opacity-50"
        >
          {loading ? (
            <>
              <RefreshCw size={18} className="animate-spin text-cyan-400" />
              <span>{t.analyzing}</span>
            </>
          ) : !currentUser ? (
            <>
              <LogIn size={18} />
              <span>{lang === 'hi' ? 'स्कैन के लिए साइन इन करें' : 'Sign in to scan'}</span>
            </>
          ) : (
            <>
              <CheckCircle2 size={18} />
              <span>{t.startScan}</span>
            </>
          )}
        </button>
      </div>

      {/* Live Progress Steps per §7.1 */}
      {loading && (
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm animate-fade-in">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 text-center">
            {t.deterministicPipeline}
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[
              { num: 1, label: t.stepUploading },
              { num: 2, label: t.stepEnhancing },
              { num: 3, label: t.stepOcr },
              { num: 4, label: t.stepRules },
            ].map((st) => (
              <div
                key={st.num}
                className={`p-3 rounded-xl border text-center transition-all ${
                  activeStep === st.num
                    ? 'bg-cyan-50 border-[#0E7490] text-[#0E7490] font-bold shadow-xs'
                    : activeStep > st.num
                    ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                    : 'bg-slate-50 border-slate-200 text-slate-400'
                }`}
              >
                <div className="text-xs font-bold">{t.stepNum} {st.num}</div>
                <div className="text-[11px] truncate mt-0.5">{st.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Webcam Modal */}
      {showWebcam && (
        <div className="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center p-4">
          <div className="relative w-full max-w-2xl bg-black rounded-2xl overflow-hidden shadow-2xl">
            <video 
              ref={videoRef} 
              autoPlay 
              playsInline 
              className="w-full h-auto max-h-[70vh] object-contain"
            />
            {/* Guide overlay */}
            <div className="absolute inset-0 border-4 border-dashed border-white/30 m-8 rounded-xl pointer-events-none"></div>
            <button 
              onClick={stopWebcam}
              className="absolute top-4 right-4 bg-black/50 hover:bg-rose-500 text-white rounded-full p-2 transition-colors"
            >
              <X size={24} />
            </button>
            <div className="absolute bottom-6 left-0 right-0 flex justify-center">
              <button 
                onClick={captureFrame}
                className="h-16 w-16 bg-white rounded-full border-4 border-slate-300 shadow-xl hover:bg-slate-100 transition-colors focus:ring-4 focus:ring-cyan-500 outline-none"
              ></button>
            </div>
          </div>
          <p className="text-white text-sm font-bold mt-4">{t.alignLabel}</p>
        </div>
      )}
    </div>
  );
};

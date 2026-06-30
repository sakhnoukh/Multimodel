import { useState, useEffect, useRef, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";
import PdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?worker";
import {
  FileText,
  Type as TypeIcon,
  Square,
  Loader2,
  ZoomIn,
  ZoomOut,
  GraduationCap,
  AlertCircle,
  Trash2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import NavRail from "../components/NavRail";
import { fetchPdfs, getPdfUrl, streamExplanation, type PdfInfo } from "../api/client";

pdfjsLib.GlobalWorkerOptions.workerPort = new PdfWorker();

interface ExplanationState {
  id: number;
  type: "text" | "image";
  content: string;
  page: number;
  explanation: string;
  streaming: boolean;
  error: string | null;
}

interface PersistedBox {
  id: number;
  page: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

function multiplyTransform(m1: number[], m2: number[]): number[] {
  return [
    m1[0] * m2[0] + m1[2] * m2[1],
    m1[1] * m2[0] + m1[3] * m2[1],
    m1[0] * m2[2] + m1[2] * m2[3],
    m1[1] * m2[2] + m1[3] * m2[3],
    m1[0] * m2[4] + m1[2] * m2[5] + m1[4],
    m1[1] * m2[4] + m1[3] * m2[5] + m1[5],
  ];
}

function PdfPage({
  pdf,
  pageNum,
  scale,
  mode,
  persistedBoxes,
  onTextSelect,
  onBoxSelect,
}: {
  pdf: pdfjsLib.PDFDocumentProxy;
  pageNum: number;
  scale: number;
  mode: "text" | "box";
  persistedBoxes: PersistedBox[];
  onTextSelect: (text: string, page: number) => void;
  onBoxSelect: (base64: string, page: number, box: Omit<PersistedBox, "id">) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [boxRect, setBoxRect] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  const boxStartRef = useRef<{ x: number; y: number } | null>(null);
  const boxEndRef = useRef<{ x: number; y: number } | null>(null);
  const isDrawingRef = useRef(false);

  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function renderPage() {
      const page = await pdf.getPage(pageNum);
      if (cancelled) return;

      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      if (!canvas) return;

      canvas.width = viewport.width;
      canvas.height = viewport.height;

      const renderTask = page.render({ canvas, viewport });
      renderTaskRef.current = renderTask;
      try {
        await renderTask.promise;
      } catch (e) {
        if (cancelled) return;
        throw e;
      }
      if (cancelled) return;

      const textContent = await page.getTextContent();
      if (cancelled) return;

      const textLayer = textLayerRef.current;
      if (textLayer) {
        textLayer.innerHTML = "";
        textLayer.style.width = `${viewport.width}px`;
        textLayer.style.height = `${viewport.height}px`;

        for (const item of textContent.items) {
          if (!("str" in item) || !(item as any).str) continue;
          const ti = item as any;
          const tx = multiplyTransform(
            viewport.transform as number[],
            (ti.transform as number[]) || [1, 0, 0, 1, 0, 0]
          );
          const fontSize = Math.hypot(tx[2], tx[3]);
          const angle = Math.atan2(tx[1], tx[0]);
          const span = document.createElement("span");
          span.textContent = ti.str;
          span.style.left = `${tx[4]}px`;
          span.style.top = `${tx[5] - fontSize}px`;
          span.style.fontSize = `${fontSize}px`;
          span.style.fontFamily = "sans-serif";
          if (angle !== 0) {
            span.style.transform = `rotate(${angle}rad)`;
            span.style.transformOrigin = "0% 0%";
          }
          textLayer.appendChild(span);
        }
      }

      if (!cancelled) setDimensions({ width: viewport.width, height: viewport.height });
    }

    renderPage();
    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel();
      renderTaskRef.current = null;
    };
  }, [pdf, pageNum, scale]);

  const handleTextMouseUp = useCallback(() => {
    if (mode !== "text") return;
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return;
    const text = selection.toString().trim();
    if (text.length < 3) return;
    onTextSelect(text, pageNum);
  }, [mode, pageNum, onTextSelect]);

  const handleBoxMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (mode !== "box") return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      boxStartRef.current = { x, y };
      boxEndRef.current = { x, y };
      isDrawingRef.current = true;
      setBoxRect({ left: x, top: y, width: 0, height: 0 });
    },
    [mode]
  );

  const handleBoxMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDrawingRef.current) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    boxEndRef.current = { x, y };
    const start = boxStartRef.current!;
    setBoxRect({
      left: Math.min(start.x, x),
      top: Math.min(start.y, y),
      width: Math.abs(x - start.x),
      height: Math.abs(y - start.y),
    });
  }, []);

  const handleBoxMouseUp = useCallback(() => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;

    const start = boxStartRef.current;
    const end = boxEndRef.current;
    setBoxRect(null);
    boxStartRef.current = null;
    boxEndRef.current = null;

    if (!start || !end) return;
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    const w = Math.abs(end.x - start.x);
    const h = Math.abs(end.y - start.y);
    if (w < 20 || h < 20) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const off = document.createElement("canvas");
    off.width = w;
    off.height = h;
    const offCtx = off.getContext("2d");
    if (!offCtx) return;
    offCtx.drawImage(canvas, x, y, w, h, 0, 0, w, h);
    const base64 = off.toDataURL("image/jpeg", 0.95).split(",")[1];
    onBoxSelect(base64, pageNum, { page: pageNum, left: x, top: y, width: w, height: h });
  }, [pageNum, onBoxSelect]);

  return (
    <div
      ref={containerRef}
      className="relative mb-4"
      style={dimensions ? { width: dimensions.width, height: dimensions.height } : { width: 400, height: 500 }}
      onMouseDown={mode === "box" ? handleBoxMouseDown : undefined}
      onMouseMove={mode === "box" ? handleBoxMouseMove : undefined}
      onMouseUp={mode === "box" ? handleBoxMouseUp : undefined}
      onMouseLeave={mode === "box" ? handleBoxMouseUp : undefined}
    >
      <canvas
        ref={canvasRef}
        className="block rounded border border-zinc-800 bg-white"
        style={dimensions ? { width: dimensions.width, height: dimensions.height } : undefined}
      />
      <div
        ref={textLayerRef}
        className="pdf-text-layer"
        style={{ pointerEvents: mode === "text" ? "auto" : "none" }}
        onMouseUp={handleTextMouseUp}
      />
      {boxRect && boxRect.width > 0 && (
        <div
          className="absolute border-2 border-cyan-400 bg-cyan-400/10 pointer-events-none z-10"
          style={{ left: boxRect.left, top: boxRect.top, width: boxRect.width, height: boxRect.height }}
        />
      )}
      {persistedBoxes.map((box) => (
        <div
          key={box.id}
          className="absolute border-2 border-cyan-500/60 bg-cyan-500/5 pointer-events-none z-10"
          style={{ left: box.left, top: box.top, width: box.width, height: box.height }}
        />
      ))}
      {!dimensions && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="animate-spin text-zinc-600" size={24} />
        </div>
      )}
    </div>
  );
}

export default function AssistedReader() {
  const [pdfs, setPdfs] = useState<Record<string, PdfInfo>>({});
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"text" | "box">("text");
  const [scale, setScale] = useState(1.5);
  const [explanations, setExplanations] = useState<ExplanationState[]>([]);
  const [boxes, setBoxes] = useState<PersistedBox[]>([]);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const nextIdRef = useRef(0);
  const prevDocRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);

  useEffect(() => {
    fetchPdfs().then((data) => {
      setPdfs(data);
      const first = Object.keys(data)[0];
      if (first && !selectedPdf) setSelectedPdf(first);
    });
  }, []);

  // Destroy previous PDF document after PdfPage components have unmounted
  useEffect(() => {
    if (prevDocRef.current && prevDocRef.current !== pdfDoc) {
      (prevDocRef.current as any)?.destroy?.();
    }
    prevDocRef.current = pdfDoc;
  }, [pdfDoc]);

  useEffect(() => {
    if (!selectedPdf) return;
    setLoading(true);
    setError(null);
    setPdfDoc(null);
    setExplanations([]);
    setBoxes([]);

    const loadingTask = pdfjsLib.getDocument({ url: getPdfUrl(selectedPdf) });
    let cancelled = false;
    let docLoaded = false;

    loadingTask.promise.then(
      (d) => {
        docLoaded = true;
        if (cancelled) { (d as any)?.destroy?.(); return; }
        setPdfDoc(d);
        setLoading(false);
      },
      (err) => {
        if (cancelled) return;
        setError(err.message || "Failed to load PDF");
        setLoading(false);
      }
    );

    return () => { cancelled = true; if (!docLoaded) loadingTask.destroy(); };
  }, [selectedPdf]);

  const requestExplanation = useCallback(
    (type: "text" | "image", content: string, page: number) => {
      if (!selectedPdf) return;
      const id = ++nextIdRef.current;
      setExplanations((prev) => [
        ...prev,
        { id, type, content, page, explanation: "", streaming: true, error: null },
      ]);

      streamExplanation(type, content, page, selectedPdf, {
        onToken: (token) => {
          setExplanations((prev) =>
            prev.map((e) => (e.id === id ? { ...e, explanation: e.explanation + token } : e))
          );
        },
        onDone: () => {
          setExplanations((prev) =>
            prev.map((e) => (e.id === id ? { ...e, streaming: false } : e))
          );
        },
        onError: (err) => {
          setExplanations((prev) =>
            prev.map((e) => (e.id === id ? { ...e, streaming: false, error: err } : e))
          );
        },
      });
    },
    [selectedPdf]
  );

  const handleTextSelect = useCallback(
    (text: string, page: number) => requestExplanation("text", text, page),
    [requestExplanation]
  );

  const handleBoxSelect = useCallback(
    (base64: string, page: number, box: Omit<PersistedBox, "id">) => {
      const boxId = ++nextIdRef.current;
      setBoxes((prev) => [...prev, { ...box, id: boxId }]);
      requestExplanation("image", base64, page);
    },
    [requestExplanation]
  );

  const clearAll = useCallback(() => {
    setExplanations([]);
    setBoxes([]);
    setCollapsed(new Set());
  }, []);

  const toggleCollapse = useCallback((id: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <div className="flex h-screen w-screen bg-zinc-950">
      <div className="w-14 flex-shrink-0 bg-zinc-900 border-r border-zinc-800">
        <NavRail />
      </div>

      {/* PDF Sidebar */}
      <div className="w-56 flex-shrink-0 bg-zinc-900 border-r border-zinc-800 flex flex-col">
        <div className="px-4 py-3 border-b border-zinc-800">
          <span className="text-sm font-semibold text-zinc-200">Reader</span>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-2">
          <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mono px-2">
            Documents
          </span>
          <div className="space-y-1 mt-1.5">
            {Object.entries(pdfs).map(([name, info]) => (
              <button
                key={name}
                onClick={() => setSelectedPdf(name)}
                className={`card w-full p-2 text-left hover:border-zinc-600 transition-colors ${
                  selectedPdf === name ? "border-cyan-700" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileText size={12} className="text-zinc-500 flex-shrink-0" />
                  <span
                    className={`text-xs truncate ${
                      selectedPdf === name ? "text-cyan-400" : "text-zinc-300"
                    }`}
                    title={name}
                  >
                    {name}
                  </span>
                </div>
                <span className="text-[10px] mono text-zinc-600 ml-5">
                  {info.element_count} elements
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* PDF View */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setMode("text")}
              className={`btn flex items-center gap-1.5 ${mode === "text" ? "btn-primary" : "btn-secondary"}`}
            >
              <TypeIcon size={14} />
              <span>Text</span>
            </button>
            <button
              onClick={() => setMode("box")}
              className={`btn flex items-center gap-1.5 ${mode === "box" ? "btn-primary" : "btn-secondary"}`}
            >
              <Square size={14} />
              <span>Box</span>
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs mono text-zinc-600">
              {pdfDoc ? `${pdfDoc.numPages} pages` : ""}
            </span>
            <button onClick={() => setScale((s) => Math.max(0.5, s - 0.25))} className="btn-secondary btn p-1.5">
              <ZoomOut size={14} />
            </button>
            <span className="text-xs mono text-zinc-500 w-12 text-center">
              {Math.round(scale * 100)}%
            </span>
            <button onClick={() => setScale((s) => Math.min(3, s + 0.25))} className="btn-secondary btn p-1.5">
              <ZoomIn size={14} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto bg-zinc-950 flex justify-center p-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3">
              <Loader2 className="animate-spin text-zinc-600" size={32} />
              <p className="text-sm text-zinc-600">Loading PDF...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center gap-3">
              <AlertCircle size={32} className="text-red-500" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          ) : pdfDoc ? (
            <div className="flex flex-col items-center">
              {Array.from({ length: pdfDoc.numPages }, (_, i) => (
                <PdfPage
                  key={`${selectedPdf}-${i + 1}`}
                  pdf={pdfDoc}
                  pageNum={i + 1}
                  scale={scale}
                  mode={mode}
                  persistedBoxes={boxes.filter((b) => b.page === i + 1)}
                  onTextSelect={handleTextSelect}
                  onBoxSelect={handleBoxSelect}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3">
              <FileText size={32} className="text-zinc-700" />
              <p className="text-sm text-zinc-600">Select a PDF to read.</p>
            </div>
          )}
        </div>
      </div>

      {/* Explanation Panel */}
      <div className="w-[420px] flex-shrink-0 bg-zinc-900 border-l border-zinc-800 flex flex-col">
        <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GraduationCap size={16} className="text-cyan-400" />
            <span className="text-sm font-semibold text-zinc-200">Explanations</span>
            {explanations.length > 0 && (
              <span className="text-[10px] mono text-zinc-600">({explanations.length})</span>
            )}
          </div>
          {explanations.length > 0 && (
            <button
              onClick={clearAll}
              className="btn-secondary btn p-1.5"
              title="Clear all"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {explanations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <GraduationCap size={32} className="text-zinc-700" />
              <p className="text-sm text-zinc-600 max-w-[280px]">
                Highlight text or draw a box on the PDF to get a detailed explanation of the
                selected content. Multiple selections will all appear here.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {explanations.map((exp) => {
                const isCollapsed = collapsed.has(exp.id);
                return (
                  <div key={exp.id} className="border-b border-zinc-800 pb-3 last:border-b-0">
                    <button
                      onClick={() => toggleCollapse(exp.id)}
                      className="w-full flex items-center gap-2 py-1.5 text-left hover:bg-zinc-800/50 rounded px-1 -mx-1"
                    >
                      {isCollapsed ? (
                        <ChevronRight size={14} className="text-zinc-500 flex-shrink-0" />
                      ) : (
                        <ChevronDown size={14} className="text-zinc-500 flex-shrink-0" />
                      )}
                      <span className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider mono flex-shrink-0">
                        {exp.type === "text" ? "Text" : "Image"}
                      </span>
                      <span className="text-[10px] mono text-zinc-600 flex-shrink-0">P{exp.page}</span>
                      {exp.streaming && (
                        <Loader2 size={12} className="animate-spin text-cyan-400 flex-shrink-0" />
                      )}
                      <span className="text-[10px] text-zinc-400 truncate ml-1">
                        {exp.type === "text"
                          ? `"${exp.content.slice(0, 60)}${exp.content.length > 60 ? "..." : ""}"`
                          : `Image region on page ${exp.page}`}
                      </span>
                    </button>

                    {!isCollapsed && (
                      <div className="space-y-2 mt-1">
                        <div className="card p-3">
                          {exp.type === "text" ? (
                            <p className="text-xs text-zinc-400 leading-relaxed line-clamp-4">
                              {exp.content}
                            </p>
                          ) : (
                            <img
                              src={`data:image/jpeg;base64,${exp.content}`}
                              alt="Selected region"
                              className="rounded border border-zinc-700 max-w-full"
                            />
                          )}
                        </div>

                        {exp.error && (
                          <div className="card p-3 border-red-900/50">
                            <div className="flex items-center gap-2 text-red-400">
                              <AlertCircle size={14} />
                              <span className="text-xs">{exp.error}</span>
                            </div>
                          </div>
                        )}

                        {exp.explanation && (
                          <div className="markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {exp.explanation}
                            </ReactMarkdown>
                          </div>
                        )}

                        {exp.streaming && (
                          <div className="flex items-center gap-2 text-zinc-500">
                            <Loader2 size={14} className="animate-spin" />
                            <span className="text-xs">Generating explanation...</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

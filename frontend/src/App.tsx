import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Archive, ArrowRight, AudioLines, BookOpen, Bot, Check, ChevronRight, CircleAlert,
  Clock3, Database, Download, FileAudio, FilePlus2, FileSearch, FileText, Folder,
  FolderOpen, Gauge, HardDrive, Inbox, Library, LoaderCircle, Menu, MessageSquareText,
  MoreHorizontal, PanelLeftClose, Play, RefreshCcw, Save, Search, Settings, ShieldCheck,
  Sparkles, Square, Upload, X, Zap,
} from 'lucide-react'

type View = 'overview' | 'import' | 'library' | 'knowledge' | 'master' | 'assistant' | 'settings'
type Status = 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'

interface Source {
  source_id: string
  original_filename: string
  stored_filename: string
  sha256: string
  file_type: 'audio' | 'document'
  extension: string
  status: Status
  language?: string
  date?: string
  duration_seconds?: number
  original_path: string
  content_path?: string
  corrected_path?: string
  warnings: string[]
  error?: string
  created_at: string
  updated_at: string
  content?: string
}

interface Job {
  job_id: string
  source_id: string
  status: Status
  progress: number
  stage: string
  error?: string
}

interface Stats {
  total_files: number
  recordings: number
  documents: number
  transcripts: number
  completed: number
  processing: number
  failed: number
  duration_seconds: number
  master_exists: boolean
}

interface AppSettings {
  workspace_path: string
  transcription_quality: 'fast' | 'balanced' | 'accurate'
  ollama_url: string
  ollama_model: string
  diarization_model_path: string
}

interface Citation { source_id: string; filename: string; timestamp?: string; excerpt: string }
interface Answer { answer: string; grounded: boolean; citations: Citation[]; mode: string }

const API = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try { message = (await response.json()).detail || message } catch { /* response was not JSON */ }
    throw new Error(message)
  }
  const contentType = response.headers.get('content-type') || ''
  return (contentType.includes('application/json') ? response.json() : response.text()) as Promise<T>
}

const nav = [
  { id: 'overview' as View, label: 'Overview', icon: Gauge },
  { id: 'import' as View, label: 'Import', icon: Upload },
  { id: 'library' as View, label: 'Source library', icon: Library },
  { id: 'knowledge' as View, label: 'Knowledge', icon: Sparkles },
  { id: 'master' as View, label: 'Master document', icon: BookOpen },
  { id: 'assistant' as View, label: 'Local assistant', icon: MessageSquareText },
]

function formatDuration(seconds = 0) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

function StatusBadge({ status }: { status: Status }) {
  const styles: Record<Status, string> = {
    completed: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300',
    processing: 'border-violet-500/20 bg-violet-500/10 text-violet-300',
    queued: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
    failed: 'border-rose-500/20 bg-rose-500/10 text-rose-300',
    cancelled: 'border-zinc-600 bg-zinc-800 text-zinc-400',
  }
  return <span className={`status ${styles[status]}`}><span className="size-1.5 rounded-full bg-current" />{status}</span>
}

function Empty({ icon: Icon, title, body, action }: { icon: typeof Inbox; title: string; body: string; action?: React.ReactNode }) {
  return <div className="flex min-h-64 flex-col items-center justify-center p-10 text-center">
    <div className="mb-4 grid size-11 place-items-center rounded-xl border border-line bg-lifted text-zinc-400"><Icon size={20} /></div>
    <h3 className="font-medium text-zinc-100">{title}</h3>
    <p className="mt-2 max-w-sm text-sm leading-6 text-zinc-500">{body}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>
}

function App() {
  const [view, setView] = useState<View>('overview')
  const [mobileNav, setMobileNav] = useState(false)
  const [sources, setSources] = useState<Source[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [stats, setStats] = useState<Stats>({ total_files: 0, recordings: 0, documents: 0, transcripts: 0, completed: 0, processing: 0, failed: 0, duration_seconds: 0, master_exists: false })
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [online, setOnline] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [globalQuery, setGlobalQuery] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [sourceData, jobData, statData, settingData] = await Promise.all([
        request<Source[]>('/sources'), request<Job[]>('/jobs'), request<Stats>('/stats'), request<AppSettings>('/settings'),
      ])
      setSources(sourceData); setJobs(jobData); setStats(statData); setSettings(settingData); setOnline(true)
    } catch { setOnline(false) }
  }, [])

  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 2500); return () => window.clearInterval(timer) }, [refresh])
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(null), 4500); return () => window.clearTimeout(timer) }, [notice])

  const navigate = (next: View) => { setView(next); setMobileNav(false) }
  const runSearch = (event: React.FormEvent) => { event.preventDefault(); if (globalQuery.trim()) navigate('library') }

  return <div className="min-h-screen bg-canvas">
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-sidebar transition-transform lg:translate-x-0 ${mobileNav ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="flex h-16 items-center gap-3 border-b border-line px-5">
        <div className="grid size-8 place-items-center rounded-lg bg-accent text-white"><AudioLines size={18} /></div>
        <div><div className="text-sm font-semibold tracking-tight">Knowledge Studio</div><div className="text-[11px] text-zinc-600">Private local workspace</div></div>
        <button className="icon-btn ml-auto lg:hidden" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button>
      </div>
      <nav className="flex-1 space-y-1 p-3" aria-label="Main navigation">
        {nav.map(item => <button key={item.id} onClick={() => navigate(item.id)} className={`flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm transition ${view === item.id ? 'bg-lifted text-zinc-100' : 'text-zinc-500 hover:bg-panel hover:text-zinc-200'}`}>
          <item.icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.id === 'import' && stats.processing > 0 && <span className="ml-auto grid size-5 place-items-center rounded-full bg-accent text-[10px] font-semibold text-white">{stats.processing}</span>}
        </button>)}
      </nav>
      <div className="border-t border-line p-3">
        <button onClick={() => navigate('settings')} className={`flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-sm transition ${view === 'settings' ? 'bg-lifted text-zinc-100' : 'text-zinc-500 hover:bg-panel hover:text-zinc-200'}`}><Settings size={17} />Settings</button>
        <div className="mt-3 rounded-lg border border-line bg-panel p-3">
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-300"><ShieldCheck size={14} className="text-emerald-400" />100% local</div>
          <p className="mt-1.5 text-[11px] leading-4 text-zinc-600">Files remain on this computer. No cloud services required.</p>
        </div>
      </div>
    </aside>

    {mobileNav && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setMobileNav(false)} />}

    <div className="lg:pl-60">
      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-canvas/95 px-4 backdrop-blur md:px-6">
        <button className="icon-btn lg:hidden" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={19} /></button>
        <form onSubmit={runSearch} className="relative max-w-lg flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" size={16} />
          <input value={globalQuery} onChange={event => setGlobalQuery(event.target.value)} className="field h-9 min-h-9 pl-9" placeholder="Search all local sources…" aria-label="Search all sources" />
        </form>
        <div className={`hidden items-center gap-2 text-xs sm:flex ${online ? 'text-zinc-500' : 'text-rose-400'}`}><span className={`size-1.5 rounded-full ${online ? 'bg-emerald-400' : 'bg-rose-400'}`} />{online ? 'Local engine ready' : 'Backend offline'}</div>
        <button className="btn btn-primary" onClick={() => navigate('import')}><FilePlus2 size={16} /><span className="hidden sm:inline">Add sources</span></button>
      </header>

      <main className="mx-auto max-w-[1480px] px-4 py-6 md:px-7 md:py-8">
        {view === 'overview' && <Overview stats={stats} sources={sources} jobs={jobs} navigate={navigate} />}
        {view === 'import' && <ImportView jobs={jobs} sources={sources} settings={settings} refresh={refresh} notify={setNotice} />}
        {view === 'library' && <LibraryView sources={sources} initialQuery={globalQuery} refresh={refresh} notify={setNotice} />}
        {view === 'knowledge' && <KnowledgeView sources={sources} navigate={navigate} />}
        {view === 'master' && <MasterView hasSources={stats.completed > 0} notify={setNotice} />}
        {view === 'assistant' && <AssistantView sources={sources} />}
        {view === 'settings' && settings && <SettingsView settings={settings} setSettings={setSettings} notify={setNotice} />}
      </main>
    </div>

    {notice && <div className="fixed bottom-5 right-5 z-50 flex max-w-md items-center gap-3 rounded-xl border border-line bg-lifted px-4 py-3 text-sm text-zinc-200 shadow-2xl"><Check size={16} className="text-emerald-400" />{notice}<button onClick={() => setNotice(null)} className="ml-2 text-zinc-600 hover:text-zinc-200"><X size={15} /></button></div>}
  </div>
}

function PageTitle({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
    <div><p className="eyebrow">{eyebrow}</p><h1 className="mt-2 text-2xl font-semibold tracking-[-.04em] text-zinc-50 md:text-[28px]">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-500">{description}</p></div>
    {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
  </div>
}

function Overview({ stats, sources, jobs, navigate }: { stats: Stats; sources: Source[]; jobs: Job[]; navigate: (v: View) => void }) {
  const metrics = [
    { label: 'Total sources', value: stats.total_files, detail: `${stats.documents} documents`, icon: Database },
    { label: 'Recordings', value: stats.recordings, detail: formatDuration(stats.duration_seconds), icon: FileAudio },
    { label: 'Processed', value: stats.completed, detail: `${stats.processing} in progress`, icon: Check },
    { label: 'Master document', value: stats.master_exists ? 'Ready' : 'Not built', detail: stats.master_exists ? 'Markdown + TXT' : 'Waiting for sources', icon: BookOpen },
  ]
  const activeJobs = jobs.filter(job => ['queued', 'processing'].includes(job.status)).slice(0, 4)
  return <>
    <PageTitle eyebrow="Workspace overview" title="Your local knowledge, in one place" description="Import recordings and documents, preserve every word, and build a traceable master knowledge file—entirely on this computer." actions={<button className="btn btn-primary" onClick={() => navigate('import')}><Upload size={16} />Import sources</button>} />
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map(metric => <div className="panel p-5" key={metric.label}><div className="flex items-start justify-between"><div><p className="text-xs font-medium text-zinc-500">{metric.label}</p><p className="mt-3 text-2xl font-semibold tracking-[-.04em] text-zinc-50">{metric.value}</p><p className="mt-1 text-xs text-zinc-600">{metric.detail}</p></div><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-400"><metric.icon size={17} /></div></div></div>)}
    </section>
    <div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-5 py-4"><div><h2 className="text-sm font-medium">Recent sources</h2><p className="mt-1 text-xs text-zinc-600">Latest activity in this workspace</p></div><button className="btn min-h-8 px-2.5 py-1 text-xs" onClick={() => navigate('library')}>View all<ArrowRight size={13} /></button></div>
        {sources.length ? <div className="divide-y divide-line">{sources.slice(0, 6).map(source => <button key={source.source_id} onClick={() => navigate('library')} className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-5 py-3.5 text-left transition hover:bg-lifted/70"><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-400">{source.file_type === 'audio' ? <FileAudio size={16} /> : <FileText size={16} />}</div><div className="min-w-0"><p className="truncate text-sm text-zinc-200">{source.original_filename}</p><p className="mt-0.5 font-mono text-[10px] text-zinc-600">{source.source_id} · {shortDate(source.created_at)}</p></div><StatusBadge status={source.status} /></button>)}</div> : <Empty icon={Inbox} title="No sources yet" body="Start with audio, Word, PDF, Markdown, subtitles, or plain text." action={<button className="btn btn-primary" onClick={() => navigate('import')}>Import files</button>} />}
      </section>
      <section className="panel p-5">
        <div className="flex items-center justify-between"><div><h2 className="text-sm font-medium">Processing pipeline</h2><p className="mt-1 text-xs text-zinc-600">One job at a time protects local resources</p></div><Zap size={17} className="text-accent" /></div>
        {activeJobs.length ? <div className="mt-5 space-y-4">{activeJobs.map(job => <div key={job.job_id}><div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="truncate text-zinc-400">{job.stage}</span><span className="font-mono text-zinc-600">{job.progress}%</span></div><div className="h-1.5 overflow-hidden rounded-full bg-zinc-800"><div className="h-full rounded-full bg-accent transition-all" style={{ width: `${job.progress}%` }} /></div></div>)}</div> : <div className="mt-6 rounded-lg border border-dashed border-line p-5 text-center"><Check className="mx-auto text-emerald-400" size={20} /><p className="mt-2 text-sm text-zinc-400">Queue is clear</p><p className="mt-1 text-xs text-zinc-600">New imports will appear here.</p></div>}
        <div className="mt-5 border-t border-line pt-4"><div className="flex items-center justify-between text-xs"><span className="text-zinc-500">Privacy status</span><span className="flex items-center gap-1.5 text-emerald-400"><ShieldCheck size={13} />Local only</span></div><div className="mt-3 flex items-center justify-between text-xs"><span className="text-zinc-500">Master export</span><span className={stats.master_exists ? 'text-zinc-300' : 'text-zinc-600'}>{stats.master_exists ? 'Up to date' : 'Not generated'}</span></div></div>
      </section>
    </div>
  </>
}

function ImportView({ jobs, sources, settings, refresh, notify }: { jobs: Job[]; sources: Source[]; settings: AppSettings | null; refresh: () => void; notify: (s: string) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [quality, setQuality] = useState(settings?.transcription_quality || 'balanced')
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)
  const addFiles = (next: FileList | File[]) => setFiles(current => {
    const unique = new Map(current.map(file => [`${file.name}-${file.size}-${file.lastModified}`, file]))
    Array.from(next).forEach(file => unique.set(`${file.name}-${file.size}-${file.lastModified}`, file))
    return Array.from(unique.values())
  })
  const upload = async () => {
    if (!files.length) return
    setUploading(true)
    const data = new FormData(); files.forEach(file => data.append('files', file)); data.append('quality', quality)
    try {
      const result = await request<{ imported: unknown[]; duplicates: unknown[]; errors: { filename: string; error: string }[] }>('/import', { method: 'POST', body: data })
      notify(`${result.imported.length} source(s) queued${result.duplicates.length ? ` · ${result.duplicates.length} duplicate(s) skipped` : ''}`)
      if (result.errors.length) notify(result.errors.map(error => `${error.filename}: ${error.error}`).join(' · '))
      setFiles([]); refresh()
    } catch (error) { notify(error instanceof Error ? error.message : 'Import failed') } finally { setUploading(false) }
  }
  const active = jobs.filter(job => ['queued', 'processing', 'failed'].includes(job.status)).slice(0, 8)
  return <>
    <PageTitle eyebrow="Local intake" title="Import source material" description="Files are copied into the active workspace, hashed for duplicates, and processed locally. Large batches are queued safely." />
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
      <div>
        <div onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files) }} className={`panel flex min-h-[300px] flex-col items-center justify-center border-dashed p-8 text-center transition ${dragging ? 'border-accent bg-accent/5' : 'hover:border-zinc-600'}`}>
          <div className="grid size-12 place-items-center rounded-xl border border-line bg-lifted text-accent"><Upload size={21} /></div><h2 className="mt-5 text-base font-medium">Drop files or folders here</h2><p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">Audio, Word, PDF, Markdown, text, SRT, and VTT. Originals remain untouched in your workspace.</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2"><button className="btn btn-primary" onClick={() => fileInput.current?.click()}><FilePlus2 size={16} />Choose files</button><button className="btn" onClick={() => folderInput.current?.click()}><Folder size={16} />Choose folder</button></div>
          <input ref={fileInput} type="file" multiple className="hidden" accept=".m4a,.mp3,.wav,.flac,.aac,.docx,.doc,.pdf,.txt,.md,.markdown,.srt,.vtt" onChange={event => event.target.files && addFiles(event.target.files)} />
          <input ref={folderInput} type="file" multiple className="hidden" {...({ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>)} onChange={event => event.target.files && addFiles(event.target.files)} />
        </div>
        {files.length > 0 && <div className="panel mt-4 overflow-hidden"><div className="flex items-center justify-between border-b border-line px-5 py-4"><div><h3 className="text-sm font-medium">Ready to import</h3><p className="mt-1 text-xs text-zinc-600">{files.length} file(s) · {(files.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024).toFixed(1)} MB</p></div><button className="text-xs text-zinc-500 hover:text-zinc-200" onClick={() => setFiles([])}>Clear list</button></div><div className="max-h-52 divide-y divide-line overflow-auto">{files.map((file, index) => <div className="flex items-center gap-3 px-5 py-3" key={`${file.name}-${index}`}><FileText size={15} className="text-zinc-500" /><span className="min-w-0 flex-1 truncate text-sm text-zinc-300">{file.webkitRelativePath || file.name}</span><span className="font-mono text-[10px] text-zinc-600">{(file.size / 1024 / 1024).toFixed(1)} MB</span><button className="text-zinc-600 hover:text-zinc-200" onClick={() => setFiles(current => current.filter((_, i) => i !== index))}><X size={15} /></button></div>)}</div><div className="flex justify-end border-t border-line p-4"><button className="btn btn-primary" disabled={uploading} onClick={upload}>{uploading ? <LoaderCircle className="animate-spin" size={16} /> : <Upload size={16} />}{uploading ? 'Copying…' : `Import ${files.length} file(s)`}</button></div></div>}
      </div>
      <aside className="space-y-4">
        <div className="panel p-5"><h3 className="text-sm font-medium">Transcription quality</h3><p className="mt-1 text-xs leading-5 text-zinc-600">Applied to audio in this batch.</p><div className="mt-4 space-y-2">{(['fast', 'balanced', 'accurate'] as const).map(mode => <button key={mode} onClick={() => setQuality(mode)} className={`w-full rounded-lg border p-3 text-left transition ${quality === mode ? 'border-accent bg-accent/10' : 'border-line bg-lifted hover:border-zinc-600'}`}><div className="flex items-center justify-between"><span className="text-sm capitalize text-zinc-200">{mode}</span>{quality === mode && <Check size={14} className="text-accent" />}</div><p className="mt-1 text-[11px] text-zinc-600">{mode === 'fast' ? 'Tiny model · lowest resource use' : mode === 'balanced' ? 'Small model · recommended default' : 'Large v3 · best accuracy, most resources'}</p></button>)}</div></div>
        <div className="panel p-5"><div className="flex items-center justify-between"><h3 className="text-sm font-medium">Processing queue</h3><span className="font-mono text-xs text-zinc-600">{active.length}</span></div>{active.length ? <div className="mt-4 space-y-3">{active.map(job => { const source = sources.find(item => item.source_id === job.source_id); return <div key={job.job_id}><div className="flex items-center justify-between gap-2"><span className="truncate text-xs text-zinc-400">{source?.original_filename || job.source_id}</span><span className="font-mono text-[10px] text-zinc-600">{job.progress}%</span></div><div className="mt-2 h-1 overflow-hidden rounded-full bg-zinc-800"><div className={`h-full ${job.status === 'failed' ? 'bg-rose-500' : 'bg-accent'}`} style={{ width: `${Math.max(job.progress, 3)}%` }} /></div></div>})}</div> : <p className="mt-4 text-xs text-zinc-600">No active processing jobs.</p>}</div>
      </aside>
    </div>
  </>
}

function LibraryView({ sources, initialQuery, refresh, notify }: { sources: Source[]; initialQuery: string; refresh: () => void; notify: (s: string) => void }) {
  const [query, setQuery] = useState(initialQuery)
  const [filter, setFilter] = useState<'all' | 'audio' | 'document'>('all')
  const [selected, setSelected] = useState<Source | null>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const filtered = sources.filter(source => (filter === 'all' || source.file_type === filter) && `${source.original_filename} ${source.source_id}`.toLowerCase().includes(query.toLowerCase()))
  const openSource = async (source: Source) => { try { const detail = await request<Source>(`/sources/${source.source_id}`); setSelected(detail); setDraft(detail.content || '') } catch (error) { notify(String(error)) } }
  const saveCorrection = async () => { if (!selected) return; try { const updated = await request<Source>(`/sources/${selected.source_id}/correction`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: draft }) }); setSelected(updated); setEditing(false); notify('Correction saved; original content preserved.'); refresh() } catch (error) { notify(String(error)) } }
  const reprocess = async (source: Source) => { await request(`/sources/${source.source_id}/reprocess`, { method: 'POST' }); notify('Source queued for reprocessing.'); refresh() }
  const archive = async (source: Source) => { if (!window.confirm(`Archive ${source.original_filename}? It will be moved to the workspace archive and can be recovered manually.`)) return; await request(`/sources/${source.source_id}`, { method: 'DELETE' }); setSelected(null); notify('Source moved to the recoverable archive.'); refresh() }
  return <>
    <PageTitle eyebrow="Source library" title="Every file, fully traceable" description="Inspect extracted content, correct transcripts without overwriting originals, retry failures, and manage the active workspace." />
    <div className="panel overflow-hidden"><div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center"><div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" size={15} /><input className="field pl-9" placeholder="Filter by filename or source ID" value={query} onChange={event => setQuery(event.target.value)} /></div><div className="flex rounded-lg border border-line bg-lifted p-1">{(['all', 'audio', 'document'] as const).map(item => <button className={`min-h-8 rounded-md px-3 text-xs capitalize transition ${filter === item ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-500 hover:text-zinc-200'}`} key={item} onClick={() => setFilter(item)}>{item}</button>)}</div></div>
      {filtered.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left"><thead><tr className="border-b border-line text-[11px] uppercase tracking-[.08em] text-zinc-600"><th className="px-5 py-3 font-medium">Source</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 font-medium">Language</th><th className="px-4 py-3 font-medium">Imported</th><th className="px-4 py-3 font-medium">Status</th><th className="w-12 px-4 py-3"><span className="sr-only">Actions</span></th></tr></thead><tbody className="divide-y divide-line">{filtered.map(source => <tr key={source.source_id} className="group transition hover:bg-lifted/70"><td className="px-5 py-3.5"><button className="flex items-center gap-3 text-left" onClick={() => openSource(source)}><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-500">{source.file_type === 'audio' ? <FileAudio size={16} /> : <FileText size={16} />}</div><div><p className="max-w-sm truncate text-sm text-zinc-200">{source.original_filename}</p><p className="mt-0.5 font-mono text-[10px] text-zinc-600">{source.source_id}</p></div></button></td><td className="px-4 py-3.5 text-xs capitalize text-zinc-500">{source.file_type}</td><td className="px-4 py-3.5 text-xs uppercase text-zinc-500">{source.language || '—'}</td><td className="px-4 py-3.5 text-xs text-zinc-500">{shortDate(source.created_at)}</td><td className="px-4 py-3.5"><StatusBadge status={source.status} /></td><td className="px-4 py-3.5"><button className="icon-btn size-8" onClick={() => openSource(source)} aria-label={`Open ${source.original_filename}`}><ChevronRight size={15} /></button></td></tr>)}</tbody></table></div> : <Empty icon={FileSearch} title="No matching sources" body="Adjust the search or file-type filter." />}
    </div>
    {selected && <div className="fixed inset-0 z-50 flex justify-end bg-black/65" onMouseDown={event => { if (event.currentTarget === event.target) setSelected(null) }}><aside className="flex h-full w-full max-w-3xl flex-col border-l border-line bg-canvas shadow-2xl"><div className="flex items-start gap-3 border-b border-line p-5"><div className="grid size-10 shrink-0 place-items-center rounded-lg border border-line bg-lifted text-zinc-400">{selected.file_type === 'audio' ? <FileAudio size={18} /> : <FileText size={18} />}</div><div className="min-w-0 flex-1"><h2 className="truncate font-medium text-zinc-100">{selected.original_filename}</h2><p className="mt-1 font-mono text-[11px] text-zinc-600">{selected.source_id} · {selected.sha256.slice(0, 16)}…</p></div><button className="icon-btn" onClick={() => setSelected(null)}><X size={18} /></button></div><div className="flex flex-wrap gap-2 border-b border-line p-4"><StatusBadge status={selected.status} />{selected.corrected_path && <span className="status border-violet-500/20 bg-violet-500/10 text-violet-300">Manual correction</span>}<div className="ml-auto flex gap-2">{selected.status === 'completed' && <button className="btn min-h-9 py-1" onClick={() => setEditing(value => !value)}>{editing ? <X size={14} /> : <Save size={14} />}{editing ? 'Cancel edit' : 'Edit content'}</button>}<button className="btn min-h-9 py-1" onClick={() => reprocess(selected)}><RefreshCcw size={14} />Reprocess</button><button className="btn min-h-9 py-1 text-rose-300" onClick={() => archive(selected)}><Archive size={14} />Archive</button></div></div>{selected.error && <div className="m-4 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"><strong>Processing error:</strong> {selected.error}</div>}{selected.warnings?.length > 0 && <div className="mx-4 mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200"><div className="flex gap-2"><CircleAlert size={15} className="shrink-0" /><div>{selected.warnings.slice(0, 4).map((warning, index) => <p key={index} className={index ? 'mt-1' : ''}>{warning}</p>)}</div></div></div>}<div className="min-h-0 flex-1 overflow-auto p-5">{editing ? <textarea className="field min-h-full resize-none py-3 font-mono text-xs leading-6" value={draft} onChange={event => setDraft(event.target.value)} /> : <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-zinc-300">{selected.content || 'No extracted content is available yet.'}</pre>}</div>{editing && <div className="flex items-center justify-between border-t border-line p-4"><p className="text-xs text-zinc-600">A new version will be saved. Machine output remains intact.</p><button className="btn btn-primary" onClick={saveCorrection}><Save size={15} />Save correction</button></div>}</aside></div>}
  </>
}

function KnowledgeView({ sources, navigate }: { sources: Source[]; navigate: (v: View) => void }) {
  const completed = sources.filter(source => source.status === 'completed')
  const uncertain = completed.filter(source => source.warnings.length)
  return <><PageTitle eyebrow="Knowledge organizer" title="Connected, without losing context" description="A conservative deterministic view of processed material. Cross-source themes are indexed, while full original content stays source-bound." actions={<button className="btn" onClick={() => navigate('master')}><BookOpen size={15} />Open master</button>} />
    <div className="grid gap-5 md:grid-cols-3"><div className="panel p-5"><div className="flex items-center gap-2 text-sm font-medium"><Sparkles size={16} className="text-accent" />Topic index</div><p className="mt-2 text-xs leading-5 text-zinc-600">Recurring lexical topics are ranked by frequency and cross-source support in the master document.</p><button className="mt-5 flex items-center gap-2 text-xs font-medium text-accent hover:text-[#9187f6]" onClick={() => navigate('master')}>Review generated topics<ArrowRight size={13} /></button></div><div className="panel p-5"><div className="flex items-center gap-2 text-sm font-medium"><Clock3 size={16} className="text-accent" />Timeline</div><p className="mt-2 text-xs leading-5 text-zinc-600">Explicit ISO and written dates are indexed with a direct source reference; dates are never guessed.</p><button className="mt-5 flex items-center gap-2 text-xs font-medium text-accent hover:text-[#9187f6]" onClick={() => navigate('master')}>Review timeline<ArrowRight size={13} /></button></div><div className="panel p-5"><div className="flex items-center gap-2 text-sm font-medium"><CircleAlert size={16} className="text-accent" />Uncertainties</div><p className="mt-2 text-xs leading-5 text-zinc-600">{uncertain.length} source(s) currently carry extraction or transcription warnings that deserve review.</p><button className="mt-5 flex items-center gap-2 text-xs font-medium text-accent hover:text-[#9187f6]" onClick={() => navigate('library')}>Inspect source warnings<ArrowRight size={13} /></button></div></div>
    <div className="panel mt-5 overflow-hidden"><div className="border-b border-line px-5 py-4"><h2 className="text-sm font-medium">Source coverage</h2><p className="mt-1 text-xs text-zinc-600">Completed material eligible for organization</p></div>{completed.length ? <div className="grid gap-px bg-line sm:grid-cols-2 xl:grid-cols-3">{completed.map(source => <div key={source.source_id} className="bg-panel p-5"><div className="flex items-start justify-between gap-3"><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-500">{source.file_type === 'audio' ? <FileAudio size={16} /> : <FileText size={16} />}</div><span className="font-mono text-[10px] text-zinc-600">{source.source_id}</span></div><p className="mt-4 truncate text-sm text-zinc-200">{source.original_filename}</p><p className="mt-1 text-xs text-zinc-600">{source.language ? `Language: ${source.language.toUpperCase()}` : 'Language not identified'}{source.duration_seconds ? ` · ${formatDuration(source.duration_seconds)}` : ''}</p></div>)}</div> : <Empty icon={Sparkles} title="Nothing organized yet" body="Processed sources will appear here and in the master document." />}</div>
  </>
}

function MasterView({ hasSources, notify }: { hasSources: boolean; notify: (s: string) => void }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const load = useCallback(async () => { setLoading(true); try { setContent(await request<string>('/master')) } finally { setLoading(false) } }, [])
  useEffect(() => { load() }, [load])
  const regenerate = async () => { await request('/master/generate', { method: 'POST' }); await load(); notify('Master document regenerated from saved sources.') }
  const occurrences = query ? content.toLowerCase().split(query.toLowerCase()).length - 1 : 0
  return <><PageTitle eyebrow="Primary export" title="Master knowledge document" description="The complete, portable Markdown output: organized indexes first, then every source in full with traceable IDs." actions={<><button className="btn" onClick={regenerate}><RefreshCcw size={15} />Regenerate</button><a className="btn btn-primary" href="/api/master/download?format=md"><Download size={15} />Download .md</a></>} />
    <div className="panel overflow-hidden"><div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center"><div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600" size={15} /><input className="field pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search inside the master document" /></div>{query && <span className="font-mono text-xs text-zinc-600">{occurrences} match(es)</span>}<a className="btn" href="/api/master/download?format=txt"><Download size={14} />TXT</a><button className="btn" onClick={async () => { await request('/workspace/open', { method: 'POST' }); notify('Opened the exports folder.') }}><FolderOpen size={14} />Open folder</button></div><div className="max-h-[calc(100vh-260px)] min-h-[480px] overflow-auto bg-[#0c0c0f] p-6 md:p-8">{loading ? <div className="flex items-center gap-2 text-sm text-zinc-500"><LoaderCircle size={16} className="animate-spin" />Loading document…</div> : hasSources ? <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-zinc-300">{content}</pre> : <Empty icon={BookOpen} title="The master document is empty" body="Import and process at least one source, then regenerate this export." />}</div></div>
  </>
}

function AssistantView({ sources }: { sources: Source[] }) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [asking, setAsking] = useState(false)
  const [showSources, setShowSources] = useState(false)
  const ask = async (event: React.FormEvent) => { event.preventDefault(); if (!question.trim()) return; setAsking(true); setAnswer(null); try { setAnswer(await request<Answer>('/assistant', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, source_ids: selected, use_ollama: true }) })) } catch (error) { setAnswer({ answer: String(error), grounded: false, citations: [], mode: 'error' }) } finally { setAsking(false) } }
  const eligible = sources.filter(source => source.status === 'completed')
  return <><PageTitle eyebrow="Grounded Q&A" title="Ask your local sources" description="Answers use only retrieved source evidence. Ollama is optional; without it, the assistant returns the most relevant cited excerpts." />
    <div className="mx-auto max-w-4xl"><div className="panel overflow-hidden"><div className="border-b border-line px-5 py-4"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-medium"><Bot size={17} className="text-accent" />Local research assistant</div><span className="status border-emerald-500/20 bg-emerald-500/10 text-emerald-300"><ShieldCheck size={12} />Grounded only</span></div></div><div className="min-h-[400px] p-5 md:p-7">{!answer && !asking && <div className="flex min-h-[330px] flex-col items-center justify-center text-center"><div className="grid size-12 place-items-center rounded-xl border border-line bg-lifted text-accent"><MessageSquareText size={21} /></div><h2 className="mt-4 text-base font-medium">What do you want to verify?</h2><p className="mt-2 max-w-md text-sm leading-6 text-zinc-500">Ask about decisions, requirements, dates, disagreements, or anything explicitly present in your files.</p><div className="mt-5 flex flex-wrap justify-center gap-2">{['What decisions were made?', 'Which questions remain open?', 'Show all mentioned dates'].map(sample => <button key={sample} className="rounded-lg border border-line bg-lifted px-3 py-2 text-xs text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200" onClick={() => setQuestion(sample)}>{sample}</button>)}</div></div>}{asking && <div className="flex min-h-[330px] flex-col items-center justify-center text-sm text-zinc-500"><LoaderCircle size={22} className="mb-3 animate-spin text-accent" />Searching local evidence…</div>}{answer && <div><div className="mb-4 flex items-center gap-2 text-xs text-zinc-600"><span className={`size-1.5 rounded-full ${answer.grounded ? 'bg-emerald-400' : 'bg-amber-400'}`} />{answer.mode === 'ollama-grounded' ? 'Synthesized by local Ollama from cited evidence' : answer.grounded ? 'Relevant excerpts from lexical search' : 'Insufficient evidence'}</div><div className="whitespace-pre-wrap text-sm leading-7 text-zinc-300">{answer.answer}</div>{answer.citations.length > 0 && <div className="mt-7 border-t border-line pt-5"><p className="eyebrow">Citations</p><div className="mt-3 grid gap-3">{answer.citations.map((citation, index) => <div key={`${citation.source_id}-${index}`} className="rounded-lg border border-line bg-lifted p-4"><div className="flex items-center gap-2"><span className="font-mono text-xs text-accent">{citation.source_id}</span>{citation.timestamp && <span className="font-mono text-[10px] text-zinc-600">@ {citation.timestamp}</span>}<span className="ml-auto max-w-[50%] truncate text-xs text-zinc-600">{citation.filename}</span></div><p className="mt-2 line-clamp-3 text-xs leading-5 text-zinc-400">{citation.excerpt}</p></div>)}</div></div>}</div>}</div><form onSubmit={ask} className="border-t border-line p-4"><div className="flex gap-2"><textarea rows={2} className="field resize-none py-2.5" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask a question about your sources…" /><button className="btn btn-primary self-end" disabled={asking || !question.trim()}><ArrowRight size={17} /></button></div><div className="mt-3 flex items-center justify-between"><button type="button" className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-200" onClick={() => setShowSources(value => !value)}><PanelLeftClose size={14} />{selected.length ? `${selected.length} source(s) selected` : 'All processed sources'}</button><span className="text-[10px] text-zinc-700">No answer without evidence</span></div>{showSources && <div className="mt-3 max-h-40 overflow-auto rounded-lg border border-line bg-lifted p-2">{eligible.map(source => <label key={source.source_id} className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-xs hover:bg-panel"><input type="checkbox" className="accent-[#7c6ff2]" checked={selected.includes(source.source_id)} onChange={event => setSelected(current => event.target.checked ? [...current, source.source_id] : current.filter(id => id !== source.source_id))} /><span className="font-mono text-zinc-600">{source.source_id}</span><span className="truncate text-zinc-400">{source.original_filename}</span></label>)}</div>}</form></div></div>
  </>
}

function SettingsView({ settings, setSettings, notify }: { settings: AppSettings; setSettings: (s: AppSettings) => void; notify: (s: string) => void }) {
  const [draft, setDraft] = useState(settings)
  const save = async () => { try { const updated = await request<AppSettings>('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) }); setSettings(updated); setDraft(updated); notify('Local settings saved.') } catch (error) { notify(error instanceof Error ? error.message : 'Could not save settings') } }
  return <><PageTitle eyebrow="Configuration" title="Local workspace settings" description="Choose where persistent files live and configure optional local models. No setting here sends content to the internet." actions={<button className="btn btn-primary" onClick={save}><Save size={15} />Save settings</button>} />
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]"><div className="space-y-5"><section className="panel p-5 md:p-6"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-400"><HardDrive size={17} /></div><div><h2 className="text-sm font-medium">Workspace location</h2><p className="mt-0.5 text-xs text-zinc-600">All originals, metadata, Markdown, and exports</p></div></div><div className="mt-5"><label className="label" htmlFor="workspace">Windows folder path</label><input id="workspace" className="field font-mono text-xs" value={draft.workspace_path} onChange={event => setDraft({ ...draft, workspace_path: event.target.value })} /><p className="mt-2 text-xs text-zinc-600">Moving an existing workspace is a manual copy operation. Select the copied folder here afterward.</p></div></section><section className="panel p-5 md:p-6"><div className="flex items-center gap-3"><div className="grid size-9 place-items-center rounded-lg border border-line bg-lifted text-zinc-400"><Bot size={17} /></div><div><h2 className="text-sm font-medium">Optional Ollama assistant</h2><p className="mt-0.5 text-xs text-zinc-600">Leave the model blank to use lexical evidence only</p></div></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><div><label className="label" htmlFor="ollama-url">Local endpoint</label><input id="ollama-url" className="field font-mono text-xs" value={draft.ollama_url} onChange={event => setDraft({ ...draft, ollama_url: event.target.value })} /></div><div><label className="label" htmlFor="ollama-model">Installed model name</label><input id="ollama-model" className="field font-mono text-xs" placeholder="e.g. llama3.2:3b" value={draft.ollama_model} onChange={event => setDraft({ ...draft, ollama_model: event.target.value })} /></div></div></section><section className="panel p-5 md:p-6"><h2 className="text-sm font-medium">Optional speaker diarization</h2><p className="mt-1 text-xs text-zinc-600">Use an already downloaded pyannote pipeline. Leave blank to disable speaker labels.</p><div className="mt-4"><label className="label" htmlFor="diarization-model">Local model folder</label><input id="diarization-model" className="field font-mono text-xs" placeholder="D:\\Models\\speaker-diarization" value={draft.diarization_model_path} onChange={event => setDraft({ ...draft, diarization_model_path: event.target.value })} /></div></section><section className="panel p-5 md:p-6"><h2 className="text-sm font-medium">Default transcription mode</h2><div className="mt-4 flex flex-wrap gap-2">{(['fast', 'balanced', 'accurate'] as const).map(quality => <button key={quality} onClick={() => setDraft({ ...draft, transcription_quality: quality })} className={`btn capitalize ${draft.transcription_quality === quality ? 'border-accent bg-accent/10 text-violet-200' : ''}`}>{quality}</button>)}</div></section></div><aside className="panel h-fit p-5"><div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck size={17} className="text-emerald-400" />Privacy guarantees</div><ul className="mt-4 space-y-3 text-xs leading-5 text-zinc-500"><li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-400" />No database server or database file</li><li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-400" />No cloud authentication or storage</li><li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-400" />Atomic JSON metadata writes</li><li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-400" />Original imports are preserved</li><li className="flex gap-2"><Check size={14} className="mt-0.5 shrink-0 text-emerald-400" />Portable relative artifact paths</li></ul></aside></div>
  </>
}

export default App


import { projects, socials } from './content.js'
import { GithubIcon, TwitterIcon, LinkedinIcon, ArrowUpRightIcon } from './icons.jsx'

const iconMap = {
  github: GithubIcon,
  twitter: TwitterIcon,
  linkedin: LinkedinIcon,
}

const accentMap = {
  amber: { dot: 'bg-amber-500', gradient: 'from-amber-200/70' },
  emerald: { dot: 'bg-emerald-500', gradient: 'from-emerald-200/70' },
  indigo: { dot: 'bg-indigo-500', gradient: 'from-indigo-200/70' },
  rose: { dot: 'bg-rose-500', gradient: 'from-rose-200/70' },
  sky: { dot: 'bg-sky-500', gradient: 'from-sky-200/70' },
  violet: { dot: 'bg-violet-500', gradient: 'from-violet-200/70' },
}
const accentOrder = ['amber', 'emerald', 'indigo', 'rose', 'sky', 'violet']

export default function App() {
  return (
    <div className="min-h-screen bg-stone-100 text-stone-900 antialiased selection:bg-amber-200 selection:text-stone-900">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-12 sm:py-16 md:grid-cols-[300px_minmax(0,1fr)] md:gap-14 lg:gap-20">
        <Sidebar />
        <ProjectsColumn />
      </div>
    </div>
  )
}

function Sidebar() {
  return (
    <aside className="md:sticky md:top-12 md:self-start">
      <div className="mb-6 h-36 w-36 overflow-hidden rounded-full shadow-sm ring-4 ring-amber-100">
        <img
          src="/founder.jpeg"
          alt="Jake Marotta"
          className="h-full w-full scale-[1.95] object-cover object-[90%_50%]"
        />
      </div>
      <h1 className="text-3xl font-black tracking-tight text-stone-900">Jake Marotta</h1>
      <div className="mt-2 flex items-center gap-3 text-sm text-stone-500">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden>📍</span> TPA
        </span>
        <span aria-hidden>·</span>
        <span>Software Engineer</span>
      </div>
      <p className="mt-5 text-stone-700 italic leading-relaxed">
        I build my own things on the side. Products and tools I&apos;d actually want to use myself.
      </p>
      <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
        </span>
        Currently building something new
      </div>
      <div className="mt-6 flex items-center gap-1">
        {socials.map((s) => {
          const Icon = iconMap[s.kind]
          return (
            <a
              key={s.kind}
              href={s.href}
              target="_blank"
              rel="noreferrer"
              aria-label={s.label}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-stone-400 transition hover:bg-white hover:text-stone-900 hover:shadow-sm"
            >
              <Icon className="h-5 w-5" />
            </a>
          )
        })}
      </div>
    </aside>
  )
}

function ProjectsColumn() {
  return (
    <section>
      <h2 className="mb-5 text-xs font-semibold uppercase tracking-[0.18em] text-stone-400">
        Projects
      </h2>
      <div
        className={
          projects.length === 1
            ? 'grid grid-cols-1'
            : 'grid grid-cols-1 gap-4 sm:grid-cols-2'
        }
      >
        {projects.map((p, i) => (
          <ProjectCard key={p.title} {...p} index={i} />
        ))}
      </div>
    </section>
  )
}

function ProjectCard({ title, description, href, tag, icon, accent: accentName, index }) {
  const accent = accentMap[accentName] || accentMap[accentOrder[index % accentOrder.length]]
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-md"
    >
      <div className="flex flex-col gap-2 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            {icon ? (
              <img src={icon} alt="" className="h-6 w-6" />
            ) : (
              <span className={`h-2.5 w-2.5 rounded-full ${accent.dot}`} />
            )}
            <h3 className="font-semibold text-stone-900">{title}</h3>
          </div>
          {tag ? (
            <span className="shrink-0 rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-600">
              {tag}
            </span>
          ) : (
            <ArrowUpRightIcon className="h-4 w-4 shrink-0 text-stone-300 transition group-hover:text-stone-900" />
          )}
        </div>
        <p className="text-sm leading-relaxed text-stone-600">{description}</p>
      </div>
      <div className={`h-20 bg-linear-to-t ${accent.gradient} to-transparent`} />
    </a>
  )
}

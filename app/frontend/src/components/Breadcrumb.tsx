import { useNavigate } from 'react-router-dom'

interface BreadcrumbProps {
  current: string
  parentPath?: string
  parentLabel?: string
}

/** Parent > Current Page breadcrumb for sub-pages accessible from a hub page. */
export default function Breadcrumb({ current, parentPath = '/settings', parentLabel = 'Settings' }: BreadcrumbProps) {
  const navigate = useNavigate()
  return (
    <nav className="breadcrumb">
      <button className="breadcrumb__link" onClick={() => navigate(parentPath)}>{parentLabel}</button>
      <span className="breadcrumb__sep">/</span>
      <span className="breadcrumb__current">{current}</span>
    </nav>
  )
}

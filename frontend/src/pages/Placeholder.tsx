export default function Placeholder({ title }: { title: string }) {
  return (
    <>
      <div className="page-header">
        <div>
          <h1>{title}</h1>
        </div>
      </div>
      <div className="content">
        <div className="card">
          <div className="empty-state">
            <p>This page is being migrated to React next. For now, the sidebar and dashboard are live.</p>
          </div>
        </div>
      </div>
    </>
  )
}

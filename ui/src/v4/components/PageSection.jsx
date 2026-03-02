export default function PageSection({ title, eyebrow, children, className = '' }) {
  const classes = ['v4-panel', className].filter(Boolean).join(' ');

  return (
    <section className={classes}>
      {(eyebrow || title) && (
        <header className="v4-panel__header">
          {eyebrow && <p className="v4-eyebrow">{eyebrow}</p>}
          {title && <h2 className="v4-panel__title">{title}</h2>}
        </header>
      )}
      {children}
    </section>
  );
}

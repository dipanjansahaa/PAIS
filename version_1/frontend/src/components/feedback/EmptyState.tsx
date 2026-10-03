interface EmptyStateProps {
  title: string;
  message?: string;
}

function EmptyState({
  title,
  message,
}: EmptyStateProps) {
  return (
    <div className="feedback-state feedback-empty">
      <div className="feedback-icon feedback-icon-empty">
        —
      </div>

      <div>
        <p className="feedback-title">{title}</p>

        {message && (
          <p className="feedback-message">
            {message}
          </p>
        )}
      </div>
    </div>
  );
}

export default EmptyState;
interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="feedback-state feedback-error">
      <div className="feedback-icon feedback-icon-error">
        !
      </div>

      <div className="feedback-content">
        <p className="feedback-title">{title}</p>

        <p className="feedback-message">
          {message}
        </p>

        {onRetry && (
          <button
            type="button"
            className="feedback-action"
            onClick={onRetry}
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export default ErrorState;
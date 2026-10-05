interface LoadingStateProps {
  message?: string;
}

function LoadingState({
  message = "Loading...",
}: LoadingStateProps) {
  return (
    <div
      className="feedback-state feedback-loading"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span
        className="loading-spinner"
        aria-hidden="true"
      />

      <div className="feedback-content">
        <p className="feedback-title">{message}</p>
      </div>
    </div>
  );
}

export default LoadingState;
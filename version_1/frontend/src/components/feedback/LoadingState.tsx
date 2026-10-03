interface LoadingStateProps {
  message?: string;
}

function LoadingState({
  message = "Loading...",
}: LoadingStateProps) {
  return (
    <div className="feedback-state feedback-loading">
      <span className="loading-spinner" aria-hidden="true" />

      <div>
        <p className="feedback-title">{message}</p>
      </div>
    </div>
  );
}

export default LoadingState;
import { useCallback, useEffect, useState } from "react";

import { getHealth } from "../lib/api";

export type ApiStatus =
  | "checking"
  | "connected"
  | "unavailable";

interface ApiStatusState {
  status: ApiStatus;
  message: string | null;
}

const HEALTH_CHECK_INTERVAL_MS = 30_000;

export function useApiStatus(): ApiStatusState {
  const [state, setState] = useState<ApiStatusState>({
    status: "checking",
    message: null,
  });

  const checkApi = useCallback(async () => {
    try {
      await getHealth();

      setState({
        status: "connected",
        message: null,
      });
    } catch (error) {
      setState({
        status: "unavailable",
        message:
          error instanceof Error
            ? error.message
            : "Unable to connect to PAIS API.",
      });
    }
  }, []);

  useEffect(() => {
    void checkApi();

    const intervalId = window.setInterval(() => {
      void checkApi();
    }, HEALTH_CHECK_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [checkApi]);

  return state;
}
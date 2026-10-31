import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  isAuthenticationError,
  request,
  subscribeAuthenticationRejection,
} from "./api";
import type { Capabilities } from "./api";

type Status =
  | "anonymous"
  | "checking"
  | "authenticated"
  | "rejected"
  | "unavailable";
const KEY = "alive-token";
function savedToken() {
  try {
    return sessionStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}
function save(token: string) {
  try {
    if (token) sessionStorage.setItem(KEY, token);
    else sessionStorage.removeItem(KEY);
  } catch {
    /* Memory-only sessions still work when storage is disabled. */
  }
}

export function useDashboardAuth() {
  const [draft, setDraft] = useState(savedToken),
    [token, setToken] = useState("");
  const [status, setStatus] = useState<Status>("anonymous"),
    [message, setMessage] = useState("");
  const accepted = useRef(""),
    entered = useRef(draft),
    generation = useRef(0);
  const controller = useRef<AbortController | null>(null),
    mounted = useRef(false);
  const isCurrent = useCallback(
    (value: string) => !!value && accepted.current === value && mounted.current,
    [],
  );
  const reject = useCallback(() => {
    generation.current++;
    controller.current?.abort();
    accepted.current = "";
    save("");
    setToken("");
    setStatus("rejected");
    setMessage("Invalid token — try again.");
  }, []);
  const validate = useCallback(
    async (candidate: string) => {
      const attempt = ++generation.current;
      controller.current?.abort();
      const c = new AbortController();
      controller.current = c;
      if (!candidate) {
        setStatus("anonymous");
        setMessage("Enter a local ALIVE bearer token.");
        return;
      }
      setStatus("checking");
      setMessage("");
      try {
        const capabilities = await request<Capabilities>(
          "/capabilities",
          candidate,
          undefined,
          "GET",
          c.signal,
        );
        if (typeof capabilities?.database?.available !== "boolean")
          throw new ApiError(
            200,
            "ALIVE returned an unexpected capabilities response.",
          );
        if (
          !mounted.current ||
          attempt !== generation.current ||
          c.signal.aborted
        )
          return;
        accepted.current = candidate;
        setToken(candidate);
        save(candidate);
        setStatus("authenticated");
        setMessage("");
      } catch (error) {
        if (
          !mounted.current ||
          attempt !== generation.current ||
          c.signal.aborted
        )
          return;
        if (isAuthenticationError(error)) reject();
        else {
          setStatus("unavailable");
          setMessage(
            "Unable to verify the connection to ALIVE. Check the backend and retry authentication.",
          );
        }
      }
    },
    [reject],
  );
  useEffect(() => {
    mounted.current = true;
    const unsubscribe = subscribeAuthenticationRejection((value) => {
      if (isCurrent(value)) reject();
    });
    const restored = entered.current;
    if (restored) void validate(restored);
    return () => {
      mounted.current = false;
      generation.current++;
      controller.current?.abort();
      unsubscribe();
    };
  }, [isCurrent, reject, validate]);
  const edit = useCallback((value: string) => {
    generation.current++;
    controller.current?.abort();
    entered.current = value;
    setDraft(value);
    if (!accepted.current) {
      save("");
      setStatus("anonymous");
      setMessage("");
    }
  }, []);
  const change = useCallback(() => {
    generation.current++;
    controller.current?.abort();
    accepted.current = "";
    entered.current = "";
    save("");
    setToken("");
    setDraft("");
    setStatus("anonymous");
    setMessage("");
  }, []);
  const report = useCallback(
    (error: unknown, usedToken: string) => {
      if (!isCurrent(usedToken)) return;
      if (isAuthenticationError(error)) reject();
      else {
        setStatus("unavailable");
        setMessage(
          "Connection to ALIVE is unavailable. Your validated session is retained; retry authentication or change token.",
        );
      }
    },
    [isCurrent, reject],
  );
  const connected = useCallback(
    (usedToken: string) => {
      if (isCurrent(usedToken)) {
        setStatus("authenticated");
        setMessage("");
      }
    },
    [isCurrent],
  );
  const retry = useCallback(
    () => validate(accepted.current || entered.current),
    [validate],
  );
  return {
    draft,
    token,
    status,
    message,
    edit,
    change,
    validate,
    retry,
    report,
    connected,
    isCurrent,
  };
}

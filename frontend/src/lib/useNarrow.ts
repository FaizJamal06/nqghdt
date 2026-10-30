// True below Tailwind's `sm` breakpoint (640px): charts show fewer x-axis labels there.
import { useSyncExternalStore } from "react";

const query = "(max-width: 639px)";

export default function useNarrow() {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
  );
}

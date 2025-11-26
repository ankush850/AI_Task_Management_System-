
import argparse
import sys
import time
import gc

MB = 1024 * 1024
PAGE = 4096  # bytes

def get_available_mb():
    try:
        import psutil
        return psutil.virtual_memory().available // MB
    except Exception:
        # psutil not available: can't read free RAM, so pretend we have plenty.
        # This disables the safety floor unless user caps with --max-mb.
        return 10**12  # effectively "infinite"

def spike_to_limit(min_free_mb=512, chunk_mb=256, touch=True, max_mb=None):
    """
    Aggressively allocate memory until:
      - available RAM <= min_free_mb (if psutil available), or
      - MemoryError occurs, or
      - max_mb cap reached (if provided).
    Returns (chunks_list, allocated_mb).
    """
    chunks = []
    allocated_mb = 0
    curr_chunk = max(1, int(chunk_mb))

    while True:
        # Stop if we've hit the cap
        if max_mb is not None and allocated_mb >= max_mb:
            break

        # Stop if we're approaching the safety floor (only works if psutil is present)
        avail = get_available_mb()
        if min_free_mb is not None and avail <= min_free_mb:
            break

        # Respect max_mb if set
        this_mb = curr_chunk
        if max_mb is not None:
            this_mb = min(this_mb, max_mb - allocated_mb)
            if this_mb <= 0:
                break

        try:
            b = bytearray(this_mb * MB)
            if touch:
                # Touch one byte per page to force commit
                for i in range(0, len(b), PAGE):
                    b[i] = 1
            chunks.append(b)
            allocated_mb += this_mb
        except MemoryError:
            # Back off to smaller chunks to top off
            if curr_chunk == 1:
                # Can't go smaller—stop here
                break
            curr_chunk = max(1, curr_chunk // 2)

    return chunks, allocated_mb

def main():
    p = argparse.ArgumentParser(description="Spike RAM usage (stress test).")
    p.add_argument("--spike", action="store_true", help="Spike memory as high as possible.")
    p.add_argument("--min-free-mb", type=int, default=512, help="Safety floor to stop at (default: 512).")
    p.add_argument("--no-safety", action="store_true", help="Ignore safety floor (may hang/crash).")
    p.add_argument("--max-mb", type=int, help="Optional hard cap on total MB to allocate.")
    p.add_argument("--chunk-mb", type=int, default=256, help="Initial chunk size MB (default: 256).")
    p.add_argument("--touch", action="store_true", help="Touch pages to force physical commit (heavier).")
    p.add_argument("--hold", type=float, default=20, help="Seconds to hold the spike (default: 20).")
    p.add_argument("--repeat", type=int, default=1, help="Repeat spike this many times (default: 1).")
    p.add_argument("--cooldown", type=float, default=10, help="Seconds between repeats (default: 10).")
    p.add_argument("--delay", type=float, default=0, help="Seconds to wait before starting.")
    p.add_argument("--wait", action="store_true", help="Wait for Enter before starting.")
    args = p.parse_args()

    if args.wait:
        input("Start your monitoring, then press Enter to spike memory...")
    if args.delay > 0:
        time.sleep(args.delay)

    # Safety handling
    min_free_mb = 0 if args.no_safety else max(0, args.min_free_mb)

    for i in range(args.repeat):
        print(f"[*] Spike {i+1}/{args.repeat}: starting (touch={args.touch}, chunk={args.chunk_mb} MB)")
        chunks, got_mb = spike_to_limit(
            min_free_mb=min_free_mb if args.spike else 0,
            chunk_mb=args.chunk_mb,
            touch=args.touch,
            max_mb=args.max_mb
        )
        print(f"[*] Allocated ~{got_mb} MB. Holding for {args.hold} seconds...")
        try:
            time.sleep(args.hold)
        except KeyboardInterrupt:
            print("\n[!] Interrupted during hold.")
        finally:
            chunks.clear()
            del chunks
            gc.collect()
            print("[*] Released memory.")

        if i < args.repeat - 1:
            print(f"[*] Cooling down for {args.cooldown} seconds...")
            time.sleep(args.cooldown)

    print("[*] Done.")

if __name__ == "__main__":
    main()
import multiprocessing
import time
import math

def cpu_intensive_task(duration):
    """
    Performs CPU-intensive calculations to create load.
    """
    end_time = time.time() + duration
    while time.time() < end_time:
        # Perform complex calculations to stress CPU
        for _ in range(10000):
            math.sqrt(math.factorial(20))
            math.sin(math.pi * 2)
            math.cos(math.pi / 4)

def create_cpu_spike(duration=10, cpu_percent=80):
    """
    Creates a CPU usage spike by running intensive tasks on multiple cores.
    
    Args:
        duration: How long the spike should last (in seconds)
        cpu_percent: Target CPU usage percentage (approximate)
    """
    cpu_count = multiprocessing.cpu_count()
    # Calculate how many cores to use based on target percentage
    cores_to_use = max(1, int(cpu_count * cpu_percent / 100))
    
    print(f"System has {cpu_count} CPU cores")
    print(f"Creating CPU spike using {cores_to_use} cores for {duration} seconds...")
    print(f"Target CPU usage: ~{cpu_percent}%")
    print("Starting CPU spike...\n")
    
    # Create processes to run on multiple cores
    processes = []
    for i in range(cores_to_use):
        p = multiprocessing.Process(target=cpu_intensive_task, args=(duration,))
        processes.append(p)
        p.start()
        print(f"Started process {i+1} on core {i+1}")
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
    
    print("\nCPU spike completed!")

if __name__ == "__main__":
    # Create a 10-second CPU spike at approximately 80% usage
    create_cpu_spike(duration=10, cpu_percent=85)
    
    print("\nWaiting 5 seconds before next spike...")
    time.sleep(5)
    
    # Create another spike at 100% for 5 seconds
    create_cpu_spike(duration=60, cpu_percent=100)

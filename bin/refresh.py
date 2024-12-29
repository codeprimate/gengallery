#!/usr/bin/env python

"""
Refresh Script

Coordinates the complete gallery processing pipeline by running:
1. Image processing
2. Gallery processing 
3. Site generation
"""

import sys
import time
from image_processor import main as process_images
from gallery_processor import main as process_galleries
from generator import main as generate_site
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def main():
    """Run the complete refresh pipeline"""
    try:
        # Show welcome banner
        title = Text("Refresh Galleries", style="bold cyan")
        console.print(Panel(title, border_style="cyan"))
        
        start_time = time.time()
        
        # Preserve original args and modify for image processor
        original_argv = sys.argv.copy()
        
        # If no gallery specified, process all
        if len(sys.argv) == 1:
            sys.argv = [sys.argv[0], '--all']
        
        # Image Processing
        img_start = time.time()
        process_images()
        img_duration = time.time() - img_start
        console.print(f"[green]✓ Image processing completed in {img_duration:.2f}s[/]")
        
        # Gallery Processing
        gallery_start = time.time()
        process_galleries()
        gallery_duration = time.time() - gallery_start
        console.print(f"[green]✓ Gallery processing completed in {gallery_duration:.2f}s[/]")
        
        # Site Generation
        site_start = time.time()
        generate_site()
        site_duration = time.time() - site_start
        console.print(f"[green]✓ Site generation completed in {site_duration:.2f}s[/]")
        
        total_duration = time.time() - start_time
        console.print(f"\n[bold green]✨ Gallery Refresh completed successfully in {total_duration:.2f}s![/]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Gallery Refresh interrupted by user[/]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Gallery Refresh failed: {str(e)}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
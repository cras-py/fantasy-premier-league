import argparse
import sys
from src.data_extraction.extractor import FPLExtractor
from src.data_extraction.pdf_report_generator import generate_pdf_report

def main():
    parser = argparse.ArgumentParser(
        description="Fantasy Premier League (FPL) Data Extraction CLI Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Perform a deep extraction fetching historical fixture/gameweek summaries for all ~700+ active players.",
    )
    
    parser.add_argument(
        "--gw",
        type=int,
        help="Fetch live gameweek stats for a specific gameweek ID (e.g. --gw 1).",
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Rate limit sleep delay (in seconds) between sequential requests to the FPL servers.",
    )

    args = parser.parse_args()

    print("==================================================")
    print("      FPL API DATA EXTRACTION SERVICE")
    print("==================================================")
    print(f"Delay: {args.delay} seconds")
    print(f"Deep Mode: {'Enabled' if args.deep else 'Disabled'}")
    if args.gw:
        print(f"Live Gameweek ID: {args.gw}")
    print("==================================================")

    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    try:
        extractor = FPLExtractor(rate_limit_delay=args.delay)
        
        # Run standard static/fixtures extraction
        extractor.run_full_extraction(deep=args.deep)
        
        # Run user and league data extraction
        team_id = os.getenv("FPL_TEAM_ID")
        league_id = os.getenv("FPL_LEAGUE_ID")
        
        if team_id:
            extractor.fetch_user_data(team_id)
        if league_id:
            extractor.fetch_league_data(league_id)
            
        # Run live gameweek stats if requested
        if args.gw:
            extractor.fetch_live_gw_data(args.gw)
            
        print("\n==================================================")
        generate_pdf_report()
        print("==================================================")
            
        print("\nExtraction process completed successfully!")
        print("Raw outputs saved in 'data/raw/'")
        print("Processed tables saved in 'data/processed/'")
        print("PDF report saved in 'src/dashboard/public/'")
        print("==================================================")
        
    except Exception as e:
        print(f"\nError occurred during extraction: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

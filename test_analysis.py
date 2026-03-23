import sys
from analyst_runtime.analysis_pipeline import run_analysis_pipeline

def test_pipeline():
    dataset_path = "datasets/Chocolate Sales (2).csv"
    question = "What is the relationship between revenue and marketing spend over the different regions, and how does it trend over time?"
    
    print(f"Testing pipeline with dataset: {dataset_path}")
    print(f"Question: {question}\n")
    
    try:
        result = run_analysis_pipeline(dataset_path, question)
        print("\n\n=== PIPELINE SUCCESS ===")
        print(f"Target: {result.get('target')}")
        print(f"Drivers: {result.get('drivers')}")
        print(f"Number of Charts: {len(result.get('charts', []))}")
        
        for i, chart in enumerate(result.get('charts', [])):
            print(f"  Chart {i+1}: {chart.get('type')} - {chart.get('description')} ({chart.get('path')})")
            
    except Exception as e:
        print(f"\n\n=== PIPELINE FAILED ===\n{e}")

if __name__ == "__main__":
    test_pipeline()

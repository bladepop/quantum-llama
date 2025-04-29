#!/bin/bash
# Example script to demonstrate using the TypeScript AST builder

# Ensure we have TypeScript installed
if ! command -v npx &> /dev/null; then
    echo "Error: npx is not installed. Please install Node.js and npm."
    exit 1
fi

# Compile and run the AST parser on our sample.ts file
echo "Compiling the TypeScript AST parser..."
cd "$(dirname "$0")/.."
npx tsc

echo -e "\nParsing the sample.ts file..."
node dist/crawler/ast_ts.js examples/sample.ts > examples/sample.ast.json

# Check if the parsing was successful
if [ $? -eq 0 ]; then
    echo -e "\nParsing successful! AST saved to examples/sample.ast.json"
    
    # Show a snippet of the output
    echo -e "\nAST Snippet (first 15 lines):"
    head -n 15 examples/sample.ast.json
    
    echo -e "\nTotal AST size in lines:"
    wc -l examples/sample.ast.json | awk '{print $1}'
else
    echo -e "\nError parsing the sample file."
    exit 1
fi 
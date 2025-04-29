#!/usr/bin/env node
/**
 * TypeScript AST parser using ts-morph.
 * Parses TypeScript source files and outputs a compact JSON representation of the AST.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as ts_morph from 'ts-morph';

/**
 * Represents a node in our simplified AST
 */
interface ASTNode {
  nodeType: string;
  name?: string;
  startLine?: number;
  endLine?: number;
  text?: string;
  docComment?: string;
  children?: ASTNode[];
  attributes?: Record<string, any>;
}

/**
 * Creates a simplified AST from a TypeScript source file
 * @param filePath Path to the TypeScript file
 * @returns A simplified AST as a JSON-serializable object
 */
function parseTypeScriptFile(filePath: string): ASTNode | { error: string } {
  try {
    if (!fs.existsSync(filePath)) {
      return { error: `File not found: ${filePath}` };
    }

    // Create a project and add the source file
    const project = new ts_morph.Project();
    const sourceFile = project.addSourceFileAtPath(filePath);

    // Create the root node (the source file itself)
    const astRoot = createNodeFromSourceFile(sourceFile);

    return astRoot;
  } catch (error) {
    return { error: `Failed to parse ${filePath}: ${error instanceof Error ? error.message : String(error)}` };
  }
}

/**
 * Creates a node in the simplified AST for a source file
 * @param sourceFile The ts-morph SourceFile
 * @returns The AST node
 */
function createNodeFromSourceFile(sourceFile: ts_morph.SourceFile): ASTNode {
  const fileNode: ASTNode = {
    nodeType: 'SourceFile',
    name: path.basename(sourceFile.getFilePath()),
    startLine: 1,
    endLine: sourceFile.getEndLineNumber(),
    children: [],
  };

  // Process all statements in the source file
  for (const statement of sourceFile.getStatements()) {
    processNode(statement, fileNode);
  }

  return fileNode;
}

/**
 * Process a ts-morph node and add it to the parent AST node
 * @param node The ts-morph Node to process
 * @param parentASTNode The parent AST node
 */
function processNode(node: ts_morph.Node, parentASTNode: ASTNode): void {
  // Skip nodes we don't care about
  if (shouldSkipNode(node)) {
    return;
  }

  const nodeKind = node.getKindName();
  let astNode: ASTNode = {
    nodeType: nodeKind,
    startLine: node.getStartLineNumber(),
    endLine: node.getEndLineNumber(),
  };

  // Add node-specific details
  addNodeSpecificDetails(node, astNode);

  // Add the node to its parent
  if (!parentASTNode.children) {
    parentASTNode.children = [];
  }
  parentASTNode.children.push(astNode);

  // Process children for container nodes
  processNodeChildren(node, astNode);
}

/**
 * Determines if a node should be skipped in the AST
 * @param node The ts-morph Node to check
 * @returns True if the node should be skipped
 */
function shouldSkipNode(node: ts_morph.Node): boolean {
  // Skip syntax that doesn't add much value to the AST
  const skipKinds = [
    ts_morph.SyntaxKind.EndOfFileToken,
    ts_morph.SyntaxKind.SemicolonToken,
    ts_morph.SyntaxKind.CommaToken,
  ];

  return skipKinds.includes(node.getKind());
}

/**
 * Add details specific to the node type
 * @param node The ts-morph Node
 * @param astNode The simplified AST node
 */
function addNodeSpecificDetails(node: ts_morph.Node, astNode: ASTNode): void {
  // Add name for named nodes
  const name = getNodeName(node);
  if (name) {
    astNode.name = name;
  }

  // Add doc comments if available
  const docComment = getNodeDocComment(node);
  if (docComment) {
    astNode.docComment = docComment;
  }

  // Add specific attributes based on node kind
  const attributes = getNodeAttributes(node);
  if (Object.keys(attributes).length > 0) {
    astNode.attributes = attributes;
  }
}

/**
 * Get the name of a node if it has one
 * @param node The ts-morph Node
 * @returns The name of the node, or undefined
 */
function getNodeName(node: ts_morph.Node): string | undefined {
  // Handle different node types
  if (ts_morph.Node.isNameableNode(node) && node.getName) {
    return node.getName();
  } else if (ts_morph.Node.isIdentifier(node)) {
    return node.getText();
  }

  return undefined;
}

/**
 * Get the documentation comment for a node
 * @param node The ts-morph Node
 * @returns The documentation comment text, or undefined
 */
function getNodeDocComment(node: ts_morph.Node): string | undefined {
  if (ts_morph.Node.isJSDocableNode(node)) {
    const jsDocs = node.getJsDocs();
    if (jsDocs.length > 0) {
      // Combine all JSDoc comments and clean them up
      return jsDocs
        .map(doc => doc.getDescription())
        .filter(desc => desc !== undefined)
        .join('\n')
        .trim();
    }
  }

  return undefined;
}

/**
 * Get attributes specific to different node types
 * @param node The ts-morph Node
 * @returns An object with node-specific attributes
 */
function getNodeAttributes(node: ts_morph.Node): Record<string, any> {
  const attributes: Record<string, any> = {};

  // Class declarations
  if (ts_morph.Node.isClassDeclaration(node)) {
    // Get heritage clauses (extends, implements)
    const extendsClause = node.getExtends();
    if (extendsClause) {
      attributes.extends = extendsClause.getText();
    }

    const implementsClauses = node.getImplements();
    if (implementsClauses.length > 0) {
      attributes.implements = implementsClauses.map(impl => impl.getText());
    }
  }
  
  // Function, method or constructor declarations
  if (ts_morph.Node.isFunctionDeclaration(node) || ts_morph.Node.isMethodDeclaration(node) || ts_morph.Node.isConstructorDeclaration(node)) {
    // Get parameters
    const parameters = node.getParameters();
    if (parameters.length > 0) {
      attributes.parameters = parameters.map(param => {
        const paramInfo: Record<string, any> = {
          name: param.getName(),
        };
        
        // Get parameter type
        const typeNode = param.getTypeNode();
        if (typeNode) {
          paramInfo.type = typeNode.getText();
        }
        
        // Get default value
        const initializer = param.getInitializer();
        if (initializer) {
          paramInfo.default = initializer.getText();
        }
        
        return paramInfo;
      });
    }
    
    // Get return type for function/method
    if (ts_morph.Node.isSignaturedDeclaration(node)) {
      const returnType = node.getReturnType();
      if (returnType && !returnType.isVoid()) {
        attributes.returnType = returnType.getText();
      }
    }
  }
  
  // Interface declarations
  if (ts_morph.Node.isInterfaceDeclaration(node)) {
    const extendsNodes = node.getExtends();
    if (extendsNodes.length > 0) {
      attributes.extends = extendsNodes.map(ext => ext.getText());
    }
  }
  
  // Variable declarations
  if (ts_morph.Node.isVariableDeclaration(node)) {
    const typeNode = node.getTypeNode();
    if (typeNode) {
      attributes.type = typeNode.getText();
    }
    
    const initializer = node.getInitializer();
    if (initializer) {
      // For simplicity, just note that it has an initializer
      attributes.hasInitializer = true;
      
      // If it's a simple literal, include the value
      if (ts_morph.Node.isStringLiteral(initializer) || 
          ts_morph.Node.isNumericLiteral(initializer) ||
          ts_morph.Node.isTrueLiteral(initializer) || 
          ts_morph.Node.isFalseLiteral(initializer)) {
        attributes.initializerValue = initializer.getText();
      }
    }
  }
  
  // Property declarations
  if (ts_morph.Node.isPropertyDeclaration(node)) {
    const typeNode = node.getTypeNode();
    if (typeNode) {
      attributes.type = typeNode.getText();
    }
    
    if (node.hasModifier('private')) {
      attributes.visibility = 'private';
    } else if (node.hasModifier('protected')) {
      attributes.visibility = 'protected';
    } else if (node.hasModifier('public')) {
      attributes.visibility = 'public';
    }
    
    if (node.isStatic()) {
      attributes.static = true;
    }
    
    if (node.isReadonly()) {
      attributes.readonly = true;
    }
  }

  return attributes;
}

/**
 * Process children of a node
 * @param node The ts-morph Node
 * @param astNode The simplified AST node
 */
function processNodeChildren(node: ts_morph.Node, astNode: ASTNode): void {
  // Process all children, depending on node type
  for (const child of node.getChildren()) {
    processNode(child, astNode);
  }
}

/**
 * Parse all TypeScript files in a directory
 * @param dirPath Path to the directory to parse
 * @param extensions Array of file extensions to include (default: ['.ts', '.tsx'])
 * @returns Object mapping file paths to their ASTs
 */
async function parseDirectory(dirPath: string, extensions: string[] = ['.ts', '.tsx']): Promise<Record<string, ASTNode | { error: string }>> {
  try {
    if (!fs.existsSync(dirPath) || !fs.statSync(dirPath).isDirectory()) {
      return { error: `Directory not found: ${dirPath}` };
    }
    
    const results: Record<string, ASTNode | { error: string }> = {};
    
    // Create a project for all files
    const project = new ts_morph.Project();
    
    // Find all TypeScript files recursively
    const files = await findFilesRecursively(dirPath, extensions);

    // Add all files to the project
    for (const file of files) {
      try {
        project.addSourceFileAtPath(file);
      } catch (error) {
        results[file] = { error: `Failed to add file to project: ${error}` };
      }
    }
    
    // Parse each file
    for (const sourceFile of project.getSourceFiles()) {
      const filePath = sourceFile.getFilePath();
      try {
        results[filePath] = createNodeFromSourceFile(sourceFile);
      } catch (error) {
        results[filePath] = { error: `Failed to parse file: ${error}` };
      }
    }
    
    return results;
  } catch (error) {
    return { error: `Failed to parse directory: ${error}` };
  }
}

/**
 * Find all files with specified extensions in a directory recursively
 */
async function findFilesRecursively(dirPath: string, extensions: string[]): Promise<string[]> {
  const files: string[] = [];
  
  async function traverse(currentPath: string) {
    try {
      const entries = await fs.promises.readdir(currentPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const entryPath = path.join(currentPath, entry.name);
        
        if (entry.isDirectory()) {
          // Skip common directories that shouldn't be processed
          if (entry.name !== 'node_modules' && entry.name !== '.git' && 
              entry.name !== 'dist' && entry.name !== '.venv') {
            await traverse(entryPath);
          }
        } else if (entry.isFile() && extensions.includes(path.extname(entry.name))) {
          files.push(entryPath);
        }
      }
    } catch (error) {
      console.error(`Error reading directory ${currentPath}: ${error}`);
    }
  }
  
  await traverse(dirPath);
  return files;
}

/**
 * Main function to run the AST parser from the command line
 */
async function main() {
  // Check for command-line arguments
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node ast_ts.js <file_or_directory_path>');
    process.exit(1);
  } 

  const targetPath = args[0];
  let result;
  
  try {
    const stats = fs.statSync(targetPath);
    
    if (stats.isFile()) {
      result = parseTypeScriptFile(targetPath);
    } else if (stats.isDirectory()) {
      // Use await since parseDirectory is now async
      result = await parseDirectory(targetPath); 
    } else {
      console.error(`Error: ${targetPath} is not a file or directory`);
      process.exit(1);
    }
    
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error(`Error: ${error}`);
    process.exit(1);
  }
}

// If running as a script (not imported as a module)
if (require.main === module) {
  main().catch(err => console.error(err));
}

// Export the functions for use as a module
export { parseTypeScriptFile, parseDirectory, ASTNode }; 
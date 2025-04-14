import re
from mistletoe.block_token import BlockToken, tokenize
import itertools
from mistletoe import span_token
from md2notion.NotionPyRenderer import NotionPyRenderer

class Document(BlockToken):
    """
    Document token.
    """
    def __init__(self, lines):
        if isinstance(lines, str):lines = lines.splitlines(keepends=True)
        lines = [line if line.endswith('\n') else '{}\n'.format(line) for line in lines]

        # add new line above and below '$$\n'
        new_lines = []
        temp_line = None
        triggered = False
        for line in lines:
            #if line.strip().replace('\n',"") =='':continue
            if not triggered and '$$\n' in line:
                temp_line = [None, line, None]
                triggered = True
            elif triggered:
                temp_line[1] += line
                if '$$\n' in line:
                    temp_line[2] = '\n'
                    new_lines.append(temp_line)
                    temp_line = None
                    triggered = False
                    
            else:
                new_lines.append([None, line, None])

        if temp_line is not None:
            new_lines.append(temp_line)
        
        
        new_lines = list(itertools.chain(*new_lines))
        new_lines = list(filter(lambda x: x is not None, new_lines))
        new_lines = ''.join(new_lines)
        lines = new_lines.splitlines(keepends=True)
        lines = [line if line.endswith('\n') else '{}\n'.format(line) for line in lines]
        #lines = [[t[1]] for  t in new_lines]
        
        
        self.footnotes = {}
        global _root_node
        _root_node = self
        span_token._root_node = self
        self.children = tokenize(lines)
        span_token._root_node = None
        _root_node = None

def read_file(file_path):
    """
    Reads a markdown file, extracts equations, renders to Notion-compatible blocks,
    and restores equations into the final rendered output.
    """
    with open(file_path, "r", encoding="utf-8") as mdFile:
        text_lines = mdFile.readlines()

        # 1. Extract and replace equations with placeholders
        equations, placeholders, text_with_placeholders = extract_equations(text_lines)

        # 2. Create Mistletoe Document and render with Notion renderer
        doc = Document(text_with_placeholders)
        with NotionPyRenderer() as renderer:
            rendered = renderer.render(doc)

        # 3. Restore equations in rendered Notion blocks
        rendered = restore_equations_in_rendered(rendered, equations, placeholders)

    return rendered

def extract_equations(text_lines):
    """
    Extracts LaTeX equations from the text and replaces them with placeholders.

    Supports both:
    - Multi-line math blocks (with standalone `$$` lines)
    - Inline math blocks (on a single line like `$$...$$`)
    """
    equations = []
    placeholders = []
    new_lines = []

    in_equation = False
    buffer = []

    for line in text_lines:
        # Handle multi-line equations that start and end with '$$' on separate lines
        if line.strip() == "$$":
            if not in_equation:
                in_equation = True
                buffer = []
            else:
                in_equation = False
                equation = "\n".join(buffer).strip()
                placeholder = f"**EQUATION_{len(equations)}**"
                equations.append(f"$$\n{equation}\n$$")
                placeholders.append(placeholder)
                new_lines.append(placeholder + "\n")
        elif in_equation:
            buffer.append(line.strip())
        else:
            # Detect and replace inline equations like '$$...$$' with placeholders
            def replace_inline_equation(match):
                equation = match.group(0)
                placeholder = f"**EQUATION_{len(equations)}**"
                equations.append(equation)
                placeholders.append(placeholder)
                return placeholder

            # 먼저 $$...$$ 처리
            modified_line = re.sub(r"\$\$(.+?)\$\$", replace_inline_equation, line)
            # 그리고 $...$ 처리 (단, 이미 $$...$$ 안에 있는 경우는 방지됨)
            modified_line = re.sub(
                r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
                replace_inline_equation,
                modified_line,
            )

            new_lines.append(modified_line)

    return equations, placeholders, new_lines

def restore_equations_in_rendered(rendered, equations, placeholders):
    """
    After rendering the document, restore equations by replacing placeholders
    in the Notion-compatible block structure.
    """
    for item in rendered:
        if "title" in item:
            for eq, ph in zip(equations, placeholders):
                item["title"] = item["title"].replace(ph, eq)
        if "children" in item:
            restore_equations_in_rendered(item["children"], equations, placeholders)
    return rendered

if __name__ == "__main__":
    for block in read_file("test.md"):
        print(block)
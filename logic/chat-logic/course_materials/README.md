# Course Materials

Drop your course documents here to give the AI Teaching Assistant context.

## Folder Structure

```
course_materials/
    syllabus.txt          --> Used in "Course FAQ" mode
    policies.txt          --> Used in "Course FAQ" mode

    assignments/
        assignment1.txt   --> Used in "Assignment Help" mode
        rubric.pdf        --> Used in "Assignment Help" mode

    lectures/
        week1_intro.txt   --> Used in "Lecture Q&A" mode
        week2_search.md   --> Used in "Lecture Q&A" mode
```

## Supported Formats

- `.txt` (plain text) - works best
- `.md` (markdown)
- `.pdf` (requires PyPDF2)
- `.docx` (requires python-docx)

## Tips

- Keep files concise (the AI has a ~12,000 character context window per mode)
- Use descriptive filenames
- Plain text works best for accuracy
- Click "Reload Materials" in the UI after adding new files

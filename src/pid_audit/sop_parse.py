import re
from docx import Document
from .schemas import SOPRecord


def parse_sop(docx_path) -> list[SOPRecord]:
    doc = Document(str(docx_path))

    table = doc.tables[0]
    records = []

    for row in table.rows:

        cells = [c.text.strip() for c in row.cells]

        # skip header and empty rows
        if not cells[0] or "pressure" in cells[0].lower():
            continue

        name = cells[0]
        pressure = parse_int(cells[1]) if len(cells) > 1 else None
        temp_min, temp_max = parse_temp(cells[2]) if len(cells) > 2 else (None, None)
        equip_id = extract_id(name)

        if not equip_id:
            continue

        records.append(SOPRecord(
            equipment_id=equip_id,
            raw_name=name,
            pressure_psig=pressure,
            temperature_min_f=temp_min,
            temperature_max_f=temp_max,
        ))

    return records


def extract_id(text: str) -> str | None:
    match = re.search(r'[A-Z]+-\d+', text.upper())
    return match.group() if match else None


def parse_int(text: str) -> int | None:
    match = re.search(r'-?\d+', text)
    return int(match.group()) if match else None


def parse_temp(text: str) -> tuple[float | None, float | None]:
    nums = [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', text)]
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)

import os
import re
from datetime import datetime
from typing import Dict, Optional, Tuple, List

try:
    from docx import Document  # type: ignore
except Exception:  # pragma: no cover - handled by caller
    Document = None  # type: ignore


class CertificateParseResult:
    def __init__(self):
        self.date_iso: Optional[str] = None  # yyyy-MM-dd
        # Cert-level
        self.calibration_reference_id: Optional[str] = None
        self.sensor_types_calibrated: List[str] = []  # e.g., ['VNIR','SWIR','RGB','LiDAR']
        # System identification
        self.system_sn: Optional[str] = None  # Chassis/System serial number (from MERGEFIELD System_SN/Chassis_SN)
        # Values by sensor type
        self.vnir_rmse_x: Optional[float] = None
        self.vnir_rmse_y: Optional[float] = None
        self.swir_rmse_x: Optional[float] = None
        self.swir_rmse_y: Optional[float] = None
        self.rgb_rmse_x: Optional[float] = None
        self.rgb_rmse_y: Optional[float] = None
        self.rgb_rmse_z: Optional[float] = None
        self.lidar_plane_fit: Optional[float] = None  # aka LiDAR_RMS
        # Hints to auto-map sensors
        self.vnir_model: Optional[str] = None
        self.vnir_sn: Optional[str] = None
        self.swir_model: Optional[str] = None
        self.swir_sn: Optional[str] = None
        self.rgb_model: Optional[str] = None
        self.rgb_sn: Optional[str] = None
        self.lidar_model: Optional[str] = None
        self.lidar_sn: Optional[str] = None
        self.gnss_model: Optional[str] = None
        self.gnss_sn: Optional[str] = None

    def to_dict_by_type(self) -> Dict[str, Dict[str, Optional[float]]]:
        out: Dict[str, Dict[str, Optional[float]]] = {}
        if self.vnir_rmse_x is not None or self.vnir_rmse_y is not None:
            out['VNIR'] = {
                'RMSE_X': self.vnir_rmse_x,
                'RMSE_Y': self.vnir_rmse_y,
            }
        if self.swir_rmse_x is not None or self.swir_rmse_y is not None:
            out['SWIR'] = {
                'RMSE_X': self.swir_rmse_x,
                'RMSE_Y': self.swir_rmse_y,
            }
        if any(v is not None for v in [self.rgb_rmse_x, self.rgb_rmse_y, self.rgb_rmse_z]):
            out['RGB'] = {
                'RMSE_X': self.rgb_rmse_x,
                'RMSE_Y': self.rgb_rmse_y,
                'RMSE_Z': self.rgb_rmse_z,
            }
        if self.lidar_plane_fit is not None:
            out['LiDAR'] = {
                'Plane_Fit': self.lidar_plane_fit,
            }
        return out


def _safe_float(s: str) -> Optional[float]:
    """Convert a string possibly containing units (e.g., '0.123 px', '1.5 cm') to float.
    Returns None if no numeric token is found.
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        try:
            return float(s)
        except Exception:
            return None
    txt = str(s).strip()
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", txt)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def parse_calibration_certificate(docx_path: str) -> Optional[CertificateParseResult]:
    """
    Parse the Calibration Certificate DOCX and pull out date and sensor metrics.
    Expected patterns (case-insensitive, flexible spacing):
      - VNIR: RMSE X: <num>, RMSE Y: <num>
      - SWIR: RMSE X: <num>, RMSE Y: <num>
      - RGB:  RMSE X: <num>, RMSE Y: <num>, RMSE Z: <num>
      - LiDAR: Plane (Fit|Fitting) RMS: <num>
    Date: try to find forms like 2025-08-28 or 2025/08/28 or 20250828. If not found, fallback to filename prefix like 20250828_...
    """
    if Document is None:
        return None

    if not os.path.isfile(docx_path):
        return None

    doc = Document(docx_path)

    # Try to parse merge fields first; seed result with them, but do not return early.
    # This allows tables/regex to fill any missing values (e.g., if fields are placeholders).
    values_from_fields = _extract_merge_field_values(doc)
    res_seed: Optional[CertificateParseResult] = None
    if values_from_fields:
        res_seed = _parse_from_merge_fields(values_from_fields, os.path.basename(docx_path))

    # Helper: iterate body elements in document order (paragraphs and tables)
    def iter_block_items(doc_):
        body = doc_.element.body
        for child in body.iterchildren():
            if child.tag.endswith('}p'):
                # Paragraph
                from docx.text.paragraph import Paragraph  # type: ignore
                yield ('p', Paragraph(child, doc_))
            elif child.tag.endswith('}tbl'):
                from docx.table import Table  # type: ignore
                yield ('t', Table(child, doc_))

    # Walk document in order to leverage section headings
    res = res_seed or CertificateParseResult()
    section: Optional[str] = None  # 'VNIR' | 'LI DAR' | 'RGB' | None
    sensor_context: Optional[str] = None  # Tracks row-level sensor context like 'GNSS'
    collected_lines: List[str] = []
    # For date and general info from tables
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    for kind, obj in iter_block_items(doc):
        if kind == 'p':
            txt = _norm(obj.text or '')
            if not txt:
                continue
            collected_lines.append(txt)
            up = txt.upper()
            if 'VNIR HYPERSPECTRAL SCANNER CALIBRATION RESULTS' in up:
                section = 'VNIR'
            elif 'SWIR HYPERSPECTRAL SCANNER CALIBRATION RESULTS' in up:
                section = 'SWIR'
            elif 'LIDAR CALIBRATION RESULTS' in up or 'LIDAR' == up:
                section = 'LIDAR'
            elif 'RGB CAMERA CALIBRATION RESULTS' in up or up == 'RGB':
                section = 'RGB'
            else:
                # keep section unchanged
                pass
        else:  # table
            tbl = obj
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells]
                if not any(cells):
                    continue
                # Append readable form to collected text for regex-based fallbacks
                collected_lines.append(' | '.join(c for c in cells if c))
                # First pass: handle rows where multiple label/value pairs exist in the same row
                # e.g., [..., 'Model', 'SBG Quanta Micro', 'Serial Number', '12345']
                up_cells = [c.upper() for c in cells]
                model_label_tokens = ['MODEL NAME', 'MODEL', 'UNIT', 'CAMERA MODEL', 'SENSOR MODEL', 'RECEIVER MODEL']
                serial_label_tokens = ['SERIAL NUMBER', 'SERIAL', 'S/N', 'SN', 'UNIT SN', 'DEVICE SN']
                # Treat any row mentioning GNSS/INS vendor/tokens as GNSS context
                is_gnss_row = any(x in ' '.join(up_cells) for x in ['GNSS', 'GNSS/INS', 'INS', 'IMU', 'NAV', 'SBG', 'QUANTA'])
                if is_gnss_row:
                    sensor_context = 'GNSS'
                for i in range(len(cells)):
                    raw_lab = cells[i]
                    lab = up_cells[i]
                    # Same-cell pattern: "Label: Value"
                    same_cell_val = None
                    m_same = re.match(r"^\s*([A-Za-z0-9 /_-]+?)\s*[:\-]\s*(.+?)\s*$", raw_lab)
                    if m_same:
                        lab = m_same.group(1).upper().strip()
                        same_cell_val = m_same.group(2).strip()
                    # Next non-empty cell as value
                    val = same_cell_val
                    if val is None:
                        for j in range(i + 1, len(cells)):
                            if cells[j].strip():
                                val = cells[j].strip()
                                break
                    if not val:
                        continue
                    if any(tok in lab for tok in model_label_tokens):
                        if section == 'VNIR' and not res.vnir_model:
                            res.vnir_model = val
                        elif section == 'SWIR' and not res.swir_model:
                            res.swir_model = val
                        elif section == 'LIDAR' and not res.lidar_model:
                            res.lidar_model = val
                        elif section == 'RGB' and not res.rgb_model:
                            res.rgb_model = val
                        elif (is_gnss_row or sensor_context == 'GNSS') and not res.gnss_model:
                            res.gnss_model = val
                            sensor_context = 'GNSS'
                    if any(tok in lab for tok in serial_label_tokens):
                        if section == 'VNIR' and not res.vnir_sn:
                            res.vnir_sn = val
                        elif section == 'SWIR' and not res.swir_sn:
                            res.swir_sn = val
                        elif section == 'LIDAR' and not res.lidar_sn:
                            res.lidar_sn = val
                        elif section == 'RGB' and not res.rgb_sn:
                            res.rgb_sn = val
                        elif (is_gnss_row or sensor_context == 'GNSS') and not res.gnss_sn:
                            res.gnss_sn = val
                # Secondary heuristic for GNSS rows: capture unlabeled serials adjacent to model
                if (is_gnss_row or sensor_context == 'GNSS') and (res.gnss_sn is None):
                    # If model already captured in this row or earlier, try to find a serial-looking token in remaining cells
                    def _looks_like_serial(s: str) -> bool:
                        ss = s.strip()
                        # Accept pure digits length>=5 or mixed alnum/hyphen length>=5
                        return bool(re.match(r"^(?:\d{5,}|[A-Za-z0-9\-]{5,})$", ss))
                    # Prefer rightmost cell as serial if it looks like a serial
                    for cand in reversed(cells):
                        if cand and _looks_like_serial(cand):
                            # Avoid picking the model string mistakenly
                            if res.gnss_model and cand.strip() != res.gnss_model:
                                res.gnss_sn = cand.strip()
                                break
                # Try to interpret as label/value
                label = None
                value = None
                if len(cells) == 2:
                    label, value = cells[0], cells[1]
                elif len(cells) >= 3:
                    # Many tables put a category in col0, label in col1, value in last
                    label = cells[0] if cells[1] == '' else cells[1]
                    value = cells[-1]
                if label:
                    labu = label.upper()
                    # General Information extraction
                    if 'GENERAL INFORMATION' in labu and 'DATE' in labu and value and not res.date_iso:
                        # value like 2025-06-17
                        try:
                            # Try multiple formats
                            for fmt in ('%Y-%m-%d','%m/%d/%Y','%Y/%m/%d'):
                                try:
                                    res.date_iso = datetime.strptime(value.strip(), fmt).strftime('%Y-%m-%d')
                                    break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    if 'GENERAL INFORMATION' in labu and 'SENSOR' in labu and value:
                        toks = [t.strip().upper() for t in re.split(r"[,;]", value) if t.strip()]
                        if toks:
                            res.sensor_types_calibrated = toks
                    if 'CALIBRATION REFERENCE ID' in labu and value and not res.calibration_reference_id:
                        # Handle cases where the value might be split across cells
                        full_value = value.strip()
                        # Check if the next cell contains additional parts of the ID
                        if i + 1 < len(cells) and cells[i + 1].strip():
                            next_val = cells[i + 1].strip()
                            # If next cell looks like part of an ID (contains underscores, dashes, or alphanumeric), append it
                            if re.match(r'^[A-Za-z0-9_\-]+$', next_val):
                                full_value += '_' + next_val
                        res.calibration_reference_id = full_value
                    # Extract system SN from table rows like "System | Headwall CoAligned HP | cAHP-191"
                    if len(cells) >= 3 and cells[0].strip().upper() == 'SYSTEM' and not res.system_sn:
                        # Third column should contain the system SN
                        potential_sn = cells[2].strip()
                        if potential_sn and re.match(r'^[A-Za-z0-9\-]+$', potential_sn):
                            res.system_sn = potential_sn
                    # Model/SN hints
                    model_label_tokens = ['MODEL NAME', 'MODEL', 'UNIT', 'CAMERA MODEL', 'SENSOR MODEL', 'RECEIVER MODEL']
                    serial_label_tokens = ['SERIAL NUMBER', 'SERIAL', 'S/N', 'SN', 'UNIT SN', 'DEVICE SN', 'RECEIVER SN', 'RECEIVER S/N']

                    # Model by section or by GNSS keywords in row
                    if any(tok in labu for tok in model_label_tokens) and value:
                        if section == 'VNIR' and not res.vnir_model:
                            res.vnir_model = value
                        elif section == 'SWIR' and not res.swir_model:
                            res.swir_model = value
                        elif section == 'LIDAR' and not res.lidar_model:
                            res.lidar_model = value
                        elif section == 'RGB' and not res.rgb_model:
                            res.rgb_model = value
                        # GNSS appears before sections; detect via row keywords
                        elif any(x in ' '.join(cells).upper() for x in ['GNSS', 'INS', 'IMU', 'NAV']) and not res.gnss_model:
                            res.gnss_model = value

                    # Serial by section or by GNSS keywords in row
                    if any(tok in labu for tok in serial_label_tokens) and value:
                        if section == 'VNIR' and not res.vnir_sn:
                            res.vnir_sn = value
                        elif section == 'SWIR' and not res.swir_sn:
                            res.swir_sn = value
                        elif section == 'LIDAR' and not res.lidar_sn:
                            res.lidar_sn = value
                        elif section == 'RGB' and not res.rgb_sn:
                            res.rgb_sn = value
                        elif any(x in ' '.join(cells).upper() for x in ['GNSS', 'GNSS/INS', 'INS', 'IMU', 'NAV']) and not res.gnss_sn:
                            res.gnss_sn = value
                    # RMSE metrics by section
                    if section == 'VNIR':
                        if 'RMSE X' in labu:
                            res.vnir_rmse_x = _safe_float(value)
                        elif 'RMSE Y' in labu:
                            res.vnir_rmse_y = _safe_float(value)
                    elif section == 'SWIR':
                        if 'RMSE X' in labu:
                            res.swir_rmse_x = _safe_float(value)
                        elif 'RMSE Y' in labu:
                            res.swir_rmse_y = _safe_float(value)
                    elif section == 'LIDAR':
                        if 'PLANE' in labu and 'RMS' in labu:
                            res.lidar_plane_fit = _safe_float(value)
                    elif section == 'RGB':
                        if 'RMSE X' in labu:
                            res.rgb_rmse_x = _safe_float(value)
                        elif 'RMSE Y' in labu:
                            res.rgb_rmse_y = _safe_float(value)
                        elif 'RMSE Z' in labu:
                            res.rgb_rmse_z = _safe_float(value)

    # Build a joined text for regex fallbacks
    full = '\n'.join(collected_lines)
    full_lc = full.lower()

    # Date detection
    date_patterns = [
        r"(20\d{2})[-/](\d{2})[-/](\d{2})",
        r"(20\d{2})(\d{2})(\d{2})",
    ]
    found_date: Optional[str] = None
    for pat in date_patterns:
        m = re.search(pat, full)
        if m:
            y, mth, d = m.group(1), m.group(2), m.group(3)
            try:
                dt = datetime(int(y), int(mth), int(d))
                found_date = dt.strftime('%Y-%m-%d')
                break
            except Exception:
                pass
    if not found_date:
        # Fallback to filename prefix like 20250828_CalibrationCertificate_v7
        base = os.path.basename(docx_path)
        m = re.match(r"(20\d{6})", base)
        if m:
            s = m.group(1)
            try:
                dt = datetime.strptime(s, '%Y%m%d')
                found_date = dt.strftime('%Y-%m-%d')
            except Exception:
                pass
    if not res.date_iso:
        res.date_iso = found_date

    # Regex fallbacks if any values still missing
    if res.vnir_rmse_x is None or res.vnir_rmse_y is None:
        m = re.search(r"vnir[\s\-:]*.*?rmse\s*x\s*[:=]\s*([\d.]+).*?rmse\s*y\s*[:=]\s*([\d.]+)", full_lc, re.IGNORECASE | re.DOTALL)
        if m:
            res.vnir_rmse_x = res.vnir_rmse_x or _safe_float(m.group(1))
            res.vnir_rmse_y = res.vnir_rmse_y or _safe_float(m.group(2))
    if res.swir_rmse_x is None or res.swir_rmse_y is None:
        m = re.search(r"swir[\s\-:]*.*?rmse\s*x\s*[:=]\s*([\d.]+).*?rmse\s*y\s*[:=]\s*([\d.]+)", full_lc, re.IGNORECASE | re.DOTALL)
        if m:
            res.swir_rmse_x = res.swir_rmse_x or _safe_float(m.group(1))
            res.swir_rmse_y = res.swir_rmse_y or _safe_float(m.group(2))
    if res.rgb_rmse_x is None or res.rgb_rmse_y is None or res.rgb_rmse_z is None:
        m = re.search(r"rgb[\s\-:]*.*?rmse\s*x\s*[:=]\s*([\d.]+).*?rmse\s*y\s*[:=]\s*([\d.]+).*?rmse\s*z\s*[:=]\s*([\d.]+)", full_lc, re.IGNORECASE | re.DOTALL)
        if m:
            res.rgb_rmse_x = res.rgb_rmse_x or _safe_float(m.group(1))
            res.rgb_rmse_y = res.rgb_rmse_y or _safe_float(m.group(2))
            res.rgb_rmse_z = res.rgb_rmse_z or _safe_float(m.group(3))
    if res.lidar_plane_fit is None:
        m = re.search(r"lidar[\s\-:]*.*?(plane\s*(fit|fitting)\s*rms|rms\s*plane\s*fit)\s*[:=]\s*([\d.]+)", full_lc, re.IGNORECASE | re.DOTALL)
        if m:
            res.lidar_plane_fit = _safe_float(m.group(3))

    # GNSS/INS regex fallback for model and SN
    if res.gnss_model is None:
        m = re.search(r"(gnss|ins|imu|gnss/ins|navigation|nav)[^\n]{0,80}?(model|unit|receiver)\s*[:\-]\s*([^\n\r]+)", full, re.IGNORECASE)
        if m:
            res.gnss_model = m.group(3).strip()
    # Detect common vendor/model tokens even without explicit labels
    if res.gnss_model is None:
        m = re.search(r"\b(sbg\s+quanta(?:\s+micro)?[\w\-]*)\b", full, re.IGNORECASE)
        if m:
            res.gnss_model = m.group(1).strip()
    if res.gnss_sn is None:
        m = re.search(r"(gnss|ins|imu|gnss/ins|navigation|nav|sbg|quanta)[^\n]{0,160}?(s/?n|serial(?:\s*number)?)\s*[:\-]\s*([^\n\r|]+)", full, re.IGNORECASE)
        if m:
            res.gnss_sn = m.group(3).strip()
    # Fallback: pipe-joined row containing model token and a serial-like field with no label
    if res.gnss_sn is None and res.gnss_model:
        # Look for a row that mentions the model, followed later by a pipe and a serial-ish token
        pattern = rf"{re.escape(res.gnss_model)}[^\n\r]*\|\s*([A-Za-z0-9\-]{{5,}})"
        m = re.search(pattern, full, re.IGNORECASE)
        if m:
            res.gnss_sn = m.group(1).strip()

    return res


def extract_merge_fields(docx_path: str) -> Dict[str, str]:
    """Public helper: returns {field_name_lower: displayed_value} for MERGEFIELDs in the DOCX.
    Returns empty dict if python-docx not available or no fields.
    """
    if Document is None:
        return {}
    if not os.path.isfile(docx_path):
        return {}
    try:
        doc = Document(docx_path)
        return _extract_merge_field_values(doc)
    except Exception:
        return {}


def _extract_merge_field_values(doc) -> Dict[str, str]:
    """Extract MERGEFIELD names and their displayed values from a Word document.
    Handles both simple fields (w:fldSimple) and complex fields (w:fldChar/instrText).
    Returns a dict of {field_name_lower: value_text}.
    """
    try:
        from docx.oxml.text.run import CT_R
        from docx.oxml import OxmlElement
    except Exception:
        return {}

    values: Dict[str, str] = {}

    # Collect all paragraphs: body, tables, headers, footers
    def all_paragraphs():
        pars = list(getattr(doc, 'paragraphs', []) or [])
        # Tables in body
        for tbl in getattr(doc, 'tables', []) or []:
            for row in getattr(tbl, 'rows', []) or []:
                for cell in getattr(row, 'cells', []) or []:
                    pars.extend(getattr(cell, 'paragraphs', []) or [])
                    # nested tables
                    for nt in getattr(cell, 'tables', []) or []:
                        for nrow in getattr(nt, 'rows', []) or []:
                            for ncell in getattr(nrow, 'cells', []) or []:
                                pars.extend(getattr(ncell, 'paragraphs', []) or [])
        # Headers/Footers
        for sec in getattr(doc, 'sections', []) or []:
            for hf in [sec.header, sec.footer]:
                if hf is None:
                    continue
                pars.extend(getattr(hf, 'paragraphs', []) or [])
                for tbl in getattr(hf, 'tables', []) or []:
                    for row in getattr(tbl, 'rows', []) or []:
                        for cell in getattr(row, 'cells', []) or []:
                            pars.extend(getattr(cell, 'paragraphs', []) or [])
        return pars

    # Helper to process a paragraph's XML runs for complex fields
    def process_paragraph_complex_fields(p) -> None:
        in_field = False
        field_name: Optional[str] = None
        capturing_value = False
        value_runs: List[str] = []

        # Iterate over python-docx runs to avoid accessing CT_P.r directly (may be absent)
        for run in getattr(p, 'runs', []) or []:
            r = run._r
            # Check for field chars
            fldChar = r.find('.//w:fldChar', r.nsmap)
            instrText = r.find('.//w:instrText', r.nsmap)
            # Begin of field
            if fldChar is not None and fldChar.get('{%s}fldCharType' % fldChar.nsmap['w']) == 'begin':
                in_field = True
                field_name = None
                capturing_value = False
                value_runs = []
                continue
            # Instruction text contains field code like ' MERGEFIELD  VNIR_RMSE_X  \* MERGEFORMAT '
            if in_field and instrText is not None:
                code = instrText.text or ''
                m = re.search(r'MERGEFIELD\s+([\w\-\.]+)', code, re.IGNORECASE)
                if m:
                    field_name = m.group(1).strip()
                continue
            # Separator indicates subsequent runs are the displayed value
            if in_field and fldChar is not None and fldChar.get('{%s}fldCharType' % fldChar.nsmap['w']) == 'separate':
                capturing_value = True
                value_runs = []
                continue
            # End indicates we can store the collected value
            if in_field and fldChar is not None and fldChar.get('{%s}fldCharType' % fldChar.nsmap['w']) == 'end':
                if field_name is not None:
                    values[field_name.lower()] = ''.join(value_runs).strip()
                in_field = False
                field_name = None
                capturing_value = False
                value_runs = []
                continue
            # Collect displayed value text
            if in_field and capturing_value:
                # Append text from t elements in this run
                ts = r.findall('.//w:t', r.nsmap)
                for t in ts:
                    if t.text:
                        value_runs.append(t.text)

    # Process complex fields in all paragraphs (body, tables, headers, footers)
    for p in all_paragraphs():
        process_paragraph_complex_fields(p)

    # Handle simple fields (fldSimple) if present
    # python-docx exposes them as <w:fldSimple w:instr="MERGEFIELD Name ..."> VALUE </w:fldSimple>
    # We scan raw XML for safety across all paragraphs
    for p in all_paragraphs():
        el = p._p
        fld_simples = el.findall('.//w:fldSimple', el.nsmap)
        for fs in fld_simples:
            instr = fs.get('{%s}instr' % fs.nsmap['w'], '')
            m = re.search(r'MERGEFIELD\s+([\w\-\.]+)', instr, re.IGNORECASE)
            if m:
                name = m.group(1).strip().lower()
                # Text value is the concatenation of descendant w:t
                ts = fs.findall('.//w:t', fs.nsmap)
                value = ''.join([t.text or '' for t in ts]).strip()
                values[name] = value
    # Also capture content controls (SDT) which may hold data by tag or alias
    try:
        root = doc.element
        nsmap = root.nsmap
        sdts = root.findall('.//w:sdt', nsmap)
        for sdt in sdts:
            # Prefer tag value, else alias value
            tag = None
            props = sdt.find('.//w:sdtPr', nsmap)
            if props is not None:
                tag_el = props.find('.//w:tag', nsmap)
                if tag_el is not None:
                    tag = tag_el.get('{%s}val' % nsmap['w'])
                if not tag:
                    alias_el = props.find('.//w:alias', nsmap)
                    if alias_el is not None:
                        tag = alias_el.get('{%s}val' % nsmap['w'])
            if not tag:
                continue
            # Extract concatenated text in the sdt's content
            content = sdt.find('.//w:sdtContent', nsmap)
            if content is None:
                continue
            ts = content.findall('.//w:t', nsmap)
            text_val = ''.join([t.text or '' for t in ts]).strip()
            if text_val:
                key = str(tag).strip().lower()
                # Do not overwrite a non-empty MERGEFIELD extraction
                if not values.get(key):
                    values[key] = text_val
    except Exception:
        pass

    return values


def _is_placeholder(val: str, field_names_lower: List[str]) -> bool:
    """Return True if val looks like an unmerged merge field placeholder like «Name» or <<Name>>.
    Compares case-insensitively against the provided candidate field names.
    """
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    # Normalize smart quotes/guillemets and angle brackets
    s_norm = s.replace('«', '<').replace('»', '>').replace('“', '"').replace('”', '"').strip()
    # Patterns: <Name>, <<Name>>, < <Name> >, etc.
    import re as _re
    m = _re.match(r"^<+\s*([A-Za-z0-9_\-\.]+)\s*>+$", s_norm)
    if not m:
        return False
    inner = m.group(1).lower()
    return inner in set(fn.lower() for fn in field_names_lower)


def _parse_from_merge_fields(vals: Dict[str, str], filename: str) -> CertificateParseResult:
    """Map merge field names to CertificateParseResult. Names are case-insensitive.
    Expected common names (examples):
      - CAL_DATE or CALIBRATION_DATE
      - VNIR_RMSE_X, VNIR_RMSE_Y
      - SWIR_RMSE_X, SWIR_RMSE_Y
      - RGB_RMSE_X, RGB_RMSE_Y, RGB_RMSE_Z
      - LIDAR_PLANE_FIT or LIDAR_PLANE_RMS
    """
    res = CertificateParseResult()

    def g(*keys: str) -> Optional[str]:
        for k in keys:
            v = vals.get(k.lower())
            if v is None:
                continue
            sv = str(v).strip()
            if not sv:
                continue
            # Skip placeholder-like values that mirror the field name (unmerged templates)
            if _is_placeholder(sv, list(keys)):
                continue
            return sv
        return None

    # Date
    cal_date = g('CAL_DATE', 'CALIBRATION_DATE', 'DATE', 'Calibration_Date')
    if cal_date:
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%m-%d-%Y', '%Y%m%d'):
            try:
                res.date_iso = datetime.strptime(cal_date, fmt).strftime('%Y-%m-%d')
                break
            except Exception:
                pass
    if not res.date_iso:
        # Fallback to filename prefix like 20250828_...
        m = re.match(r"(20\d{6})", filename)
        if m:
            try:
                dt = datetime.strptime(m.group(1), '%Y%m%d')
                res.date_iso = dt.strftime('%Y-%m-%d')
            except Exception:
                pass

    # Certificate-wide hints
    res.calibration_reference_id = g('Calibration_Reference_ID', 'CALIBRATION_REFERENCE_ID', 'CAL_REF_ID')
    # Sensor types list (comma/space separated)
    stc = g('Sensor_Types_Calibrated', 'SENSOR_TYPES_CALIBRATED')
    if stc:
        # Normalize tokens like "VNIR; SWIR, RGB lidar"
        tokens = re.split(r"[;,\s]+", stc)
        res.sensor_types_calibrated = [t.strip().upper() for t in tokens if t.strip()]

    # System/Chassis SN
    # Common variants seen across templates
    res.system_sn = g(
        'System_SN', 'SYSTEM_SN', 'System', 'SYSTEM', 'System_Serial', 'System_Serial_Number', 'SystemSerial',
        'Chassis_SN', 'CHASSIS_SN', 'Chassis', 'CHASSIS', 'Chassis_Serial', 'Chassis_Serial_Number', 'chassis_sn'
    )

    # Per-sensor Model/SN hints
    # GNSS/INS/IMU/NAV model variants
    res.gnss_model = g(
        'GNSS_Model', 'GNSS_Model_Name', 'GNSS', 'GNSS_Receiver', 'GNSS_Receiver_Model', 'GNSS_Unit',
        'INS_Model', 'INS_Model_Name', 'INS', 'IMU_Model', 'IMU_Model_Name', 'IMU',
        'NAV_Model', 'NAV_Model_Name', 'Navigation_Model', 'Navigation_Unit', 'Navigation'
    )
    # GNSS serial variants
    res.gnss_sn = g(
        'GNSS_SN', 'GNSS_Serial', 'GNSS_Serial_Number', 'GNSS_Receiver_SN', 'GNSS_Receiver_Serial', 'GNSS_Unit_SN',
        'INS_SN', 'INS_Serial', 'IMU_SN', 'IMU_Serial', 'NAV_SN', 'NAV_Serial', 'Receiver_SN', 'Receiver_Serial', 'Unit_SN', 'Device_SN'
    )
    # VNIR
    res.vnir_model = g('VNIR_Model', 'VNIR_Model_Name', 'VNIR', 'VNIR_Camera_Model')
    res.vnir_sn = g('VNIR_SN', 'VNIR_Serial', 'VNIR_Serial_Number')
    # SWIR
    res.swir_model = g('SWIR_Model', 'SWIR_Model_Name', 'SWIR', 'SWIR_Camera_Model')
    res.swir_sn = g('SWIR_SN', 'SWIR_Serial', 'SWIR_Serial_Number')
    # LiDAR
    res.lidar_model = g('LiDAR_Model', 'LIDAR_Model', 'LiDAR', 'LIDAR_Sensor_Model')
    res.lidar_sn = g('LiDAR_SN', 'LIDAR_SN', 'LiDAR_Serial', 'LIDAR_Serial_Number')
    # RGB
    res.rgb_model = g('RGB_Model', 'RGB_Model_Name', 'RGB', 'RGB_Camera_Model')
    res.rgb_sn = g('RGB_SN', 'RGB_Serial', 'RGB_Serial_Number')

    # VNIR
    res.vnir_rmse_x = _safe_float(g('VNIR_RMSE_X', 'VNIR_X'))
    res.vnir_rmse_y = _safe_float(g('VNIR_RMSE_Y', 'VNIR_Y'))
    # SWIR
    res.swir_rmse_x = _safe_float(g('SWIR_RMSE_X', 'SWIR_X'))
    res.swir_rmse_y = _safe_float(g('SWIR_RMSE_Y', 'SWIR_Y'))
    # RGB
    res.rgb_rmse_x = _safe_float(g('RGB_RMSE_X', 'RGB_X'))
    res.rgb_rmse_y = _safe_float(g('RGB_RMSE_Y', 'RGB_Y'))
    res.rgb_rmse_z = _safe_float(g('RGB_RMSE_Z', 'RGB_Z'))
    # LiDAR
    res.lidar_plane_fit = _safe_float(g('LIDAR_PLANE_FIT', 'LIDAR_PLANE_RMS', 'PLANE_FIT', 'LiDAR_RMS', 'LIDAR_RMS'))

    return res

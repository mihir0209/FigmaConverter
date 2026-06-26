"""Map Figma component types to UI library primitives.

Supported component libraries:
- shadcn/ui (React) — radix primitives with shadcn conventions
- MUI (React)
- Ant Design (React)
- Bootstrap 5 (HTML / React)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Mapping tables — keywords that hint at a component's role in Figma
# ---------------------------------------------------------------------------

_LIBRARY_MAPS: Dict[str, Dict[str, Any]] = {
    "shadcn": {
        "components": {
            "button": {
                "name": "Button",
                "import_from": "@/components/ui/button",
                "props_hint": 'variant="outline" | "ghost" | "link" | "default"',
            },
            "card": {
                "name": "Card",
                "import_from": "@/components/ui/card",
                "props_hint": "Card, CardHeader, CardContent, CardFooter",
            },
            "input": {
                "name": "Input",
                "import_from": "@/components/ui/input",
                "props_hint": 'type="text" placeholder="…"',
            },
            "textarea": {
                "name": "Textarea",
                "import_from": "@/components/ui/textarea",
                "props_hint": 'placeholder="…"',
            },
            "select": {
                "name": "Select",
                "import_from": "@/components/ui/select",
                "props_hint": "Select, SelectTrigger, SelectValue, SelectContent, SelectItem",
            },
            "dialog": {
                "name": "Dialog",
                "import_from": "@/components/ui/dialog",
                "props_hint": "Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle",
            },
            "modal": {
                "name": "Dialog",
                "import_from": "@/components/ui/dialog",
                "props_hint": "Dialog, DialogTrigger, DialogContent",
            },
            "avatar": {
                "name": "Avatar",
                "import_from": "@/components/ui/avatar",
                "props_hint": "Avatar, AvatarImage, AvatarFallback",
            },
            "badge": {
                "name": "Badge",
                "import_from": "@/components/ui/badge",
                "props_hint": 'variant="secondary" | "outline"',
            },
            "checkbox": {
                "name": "Checkbox",
                "import_from": "@/components/ui/checkbox",
                "props_hint": "",
            },
            "switch": {
                "name": "Switch",
                "import_from": "@/components/ui/switch",
                "props_hint": "",
            },
            "radio": {
                "name": "RadioGroup",
                "import_from": "@/components/ui/radio-group",
                "props_hint": "RadioGroup, RadioGroupItem",
            },
            "tabs": {
                "name": "Tabs",
                "import_from": "@/components/ui/tabs",
                "props_hint": "Tabs, TabsList, TabsTrigger, TabsContent",
            },
            "table": {
                "name": "Table",
                "import_from": "@/components/ui/table",
                "props_hint": "Table, TableHeader, TableBody, TableRow, TableCell",
            },
            "separator": {
                "name": "Separator",
                "import_from": "@/components/ui/separator",
                "props_hint": "",
            },
            "tooltip": {
                "name": "Tooltip",
                "import_from": "@/components/ui/tooltip",
                "props_hint": "Tooltip, TooltipTrigger, TooltipContent",
            },
            "label": {
                "name": "Label",
                "import_from": "@/components/ui/label",
                "props_hint": "",
            },
            "progress": {
                "name": "Progress",
                "import_from": "@/components/ui/progress",
                "props_hint": 'value={0-100}',
            },
            "skeleton": {
                "name": "Skeleton",
                "import_from": "@/components/ui/skeleton",
                "props_hint": 'className="w-… h-…"',
            },
            "toast": {
                "name": "Toast",
                "import_from": "@/components/ui/toast",
                "props_hint": "Toast, ToastProvider, ToastViewport",
            },
        },
        "keywords": {
            "btn": "button",
            "cta": "button",
            "action": "button",
            "submit": "button",
            "iconbutton": "button",
            "primary": "button",
            "secondary": "button",
            "input": "input",
            "textfield": "input",
            "search": "input",
            "textarea": "textarea",
            "dropdown": "select",
            "picker": "select",
            "option": "select",
            "dialog": "dialog",
            "modal": "modal",
            "popup": "dialog",
            "overlay": "dialog",
            "avatar": "avatar",
            "profilepic": "avatar",
            "badge": "badge",
            "pill": "badge",
            "chip": "badge",
            "tag": "badge",
            "checkbox": "checkbox",
            "switch": "switch",
            "toggle": "switch",
            "radio": "radio",
            "tab": "tabs",
            "table": "table",
            "grid": "table",
            "divider": "separator",
            "separator": "separator",
            "hr": "separator",
            "tooltip": "tooltip",
            "hint": "tooltip",
            "progress": "progress",
            "spinner": "progress",
            "loader": "progress",
            "loading": "progress",
            "skeleton": "skeleton",
            "placeholder": "skeleton",
            "toast": "toast",
            "notification": "toast",
            "alert": "toast",
            "snackbar": "toast",
            "label": "label",
            "card": "card",
            "tile": "card",
            "panel": "card",
            "container": "card",
        },
        "fallback_element": "div",
        "framework_hint": "react_ts",
    },
    "mui": {
        "components": {
            "button": {
                "name": "Button",
                "import_from": "@mui/material/Button",
                "props_hint": 'variant="contained" | "outlined" | "text" color="primary"',
            },
            "card": {
                "name": "Card",
                "import_from": "@mui/material/Card",
                "props_hint": "Card, CardContent, CardActions, CardMedia",
            },
            "input": {
                "name": "TextField",
                "import_from": "@mui/material/TextField",
                "props_hint": 'variant="outlined" | "filled" | "standard"',
            },
            "textarea": {
                "name": "TextField",
                "import_from": "@mui/material/TextField",
                "props_hint": 'multiline rows={4}',
            },
            "select": {
                "name": "Select",
                "import_from": "@mui/material/Select",
                "props_hint": "Select, MenuItem",
            },
            "dialog": {
                "name": "Dialog",
                "import_from": "@mui/material/Dialog",
                "props_hint": "Dialog, DialogTitle, DialogContent, DialogActions",
            },
            "modal": {
                "name": "Modal",
                "import_from": "@mui/material/Modal",
                "props_hint": "",
            },
            "avatar": {
                "name": "Avatar",
                "import_from": "@mui/material/Avatar",
                "props_hint": "",
            },
            "badge": {
                "name": "Badge",
                "import_from": "@mui/material/Badge",
                "props_hint": 'badgeContent={…}',
            },
            "checkbox": {
                "name": "Checkbox",
                "import_from": "@mui/material/Checkbox",
                "props_hint": "",
            },
            "switch": {
                "name": "Switch",
                "import_from": "@mui/material/Switch",
                "props_hint": "",
            },
            "radio": {
                "name": "RadioGroup",
                "import_from": "@mui/material/RadioGroup",
                "props_hint": "RadioGroup, FormControlLabel, Radio",
            },
            "tabs": {
                "name": "Tabs",
                "import_from": "@mui/material/Tabs",
                "props_hint": "Tabs, Tab",
            },
            "table": {
                "name": "Table",
                "import_from": "@mui/material/Table",
                "props_hint": "Table, TableHead, TableBody, TableRow, TableCell",
            },
            "divider": {
                "name": "Divider",
                "import_from": "@mui/material/Divider",
                "props_hint": "",
            },
            "tooltip": {
                "name": "Tooltip",
                "import_from": "@mui/material/Tooltip",
                "props_hint": 'title="…"',
            },
            "progress": {
                "name": "CircularProgress",
                "import_from": "@mui/material/CircularProgress",
                "props_hint": "",
            },
            "linear_progress": {
                "name": "LinearProgress",
                "import_from": "@mui/material/LinearProgress",
                "props_hint": "",
            },
            "chip": {
                "name": "Chip",
                "import_from": "@mui/material/Chip",
                "props_hint": 'label="…" variant="outlined" | "filled"',
            },
            "snackbar": {
                "name": "Snackbar",
                "import_from": "@mui/material/Snackbar",
                "props_hint": "Snackbar, Alert",
            },
            "icon_button": {
                "name": "IconButton",
                "import_from": "@mui/material/IconButton",
                "props_hint": "",
            },
            "typography": {
                "name": "Typography",
                "import_from": "@mui/material/Typography",
                "props_hint": 'variant="h1" | "h2" | "body1" | "body2"',
            },
            "box": {
                "name": "Box",
                "import_from": "@mui/material/Box",
                "props_hint": 'sx={{ … }}',
            },
            "stack": {
                "name": "Stack",
                "import_from": "@mui/material/Stack",
                "props_hint": 'direction="row" | "column" spacing={2}',
            },
            "grid": {
                "name": "Grid",
                "import_from": "@mui/material/Grid",
                "props_hint": "",
            },
            "container": {
                "name": "Container",
                "import_from": "@mui/material/Container",
                "props_hint": 'maxWidth="lg"',
            },
        },
        "keywords": {
            "btn": "button",
            "cta": "button",
            "action": "button",
            "submit": "button",
            "iconbutton": "icon_button",
            "fab": "button",
            "input": "input",
            "textfield": "input",
            "search": "input",
            "textarea": "textarea",
            "dropdown": "select",
            "picker": "select",
            "option": "select",
            "dialog": "dialog",
            "modal": "modal",
            "popup": "dialog",
            "overlay": "modal",
            "avatar": "avatar",
            "profilepic": "avatar",
            "badge": "badge",
            "pill": "chip",
            "chip": "chip",
            "tag": "chip",
            "checkbox": "checkbox",
            "switch": "switch",
            "toggle": "switch",
            "radio": "radio",
            "tab": "tabs",
            "table": "table",
            "divider": "divider",
            "separator": "divider",
            "hr": "divider",
            "tooltip": "tooltip",
            "hint": "tooltip",
            "progress": "progress",
            "spinner": "progress",
            "loader": "progress",
            "loading": "progress",
            "skeleton": "linear_progress",
            "toast": "snackbar",
            "notification": "snackbar",
            "alert": "snackbar",
            "snackbar": "snackbar",
            "label": "typography",
            "card": "card",
            "tile": "card",
            "panel": "card",
            "container": "container",
            "typography": "typography",
            "text": "typography",
            "heading": "typography",
            "title": "typography",
            "stack": "stack",
            "flex": "stack",
            "row": "stack",
            "grid": "grid",
        },
        "fallback_element": "Box",
        "framework_hint": "react_ts",
    },
    "antd": {
        "components": {
            "button": {
                "name": "Button",
                "import_from": "antd",
                "props_hint": 'type="primary" | "dashed" | "link" | "text"',
            },
            "card": {
                "name": "Card",
                "import_from": "antd",
                "props_hint": "title={…} bordered",
            },
            "input": {
                "name": "Input",
                "import_from": "antd",
                "props_hint": 'placeholder="…"',
            },
            "textarea": {
                "name": "Input.TextArea",
                "import_from": "antd",
                "props_hint": 'rows={4}',
            },
            "select": {
                "name": "Select",
                "import_from": "antd",
                "props_hint": "mode='multiple' | undefined",
            },
            "modal": {
                "name": "Modal",
                "import_from": "antd",
                "props_hint": "Modal, Modal.confirm()",
            },
            "dialog": {
                "name": "Modal",
                "import_from": "antd",
                "props_hint": "Modal, Modal.confirm()",
            },
            "avatar": {
                "name": "Avatar",
                "import_from": "antd",
                "props_hint": 'src="…"',
            },
            "badge": {
                "name": "Badge",
                "import_from": "antd",
                "props_hint": "count={…}",
            },
            "checkbox": {
                "name": "Checkbox",
                "import_from": "antd",
                "props_hint": "",
            },
            "switch": {
                "name": "Switch",
                "import_from": "antd",
                "props_hint": "",
            },
            "radio": {
                "name": "Radio",
                "import_from": "antd",
                "props_hint": "Radio, Radio.Group",
            },
            "tabs": {
                "name": "Tabs",
                "import_from": "antd",
                "props_hint": "Tabs, TabPane",
            },
            "table": {
                "name": "Table",
                "import_from": "antd",
                "props_hint": "columns={…} dataSource={…}",
            },
            "divider": {
                "name": "Divider",
                "import_from": "antd",
                "props_hint": "",
            },
            "tooltip": {
                "name": "Tooltip",
                "import_from": "antd",
                "props_hint": 'title="…"',
            },
            "progress": {
                "name": "Progress",
                "import_from": "antd",
                "props_hint": 'percent={…} type="circle" | "line"',
            },
            "tag": {
                "name": "Tag",
                "import_from": "antd",
                "props_hint": "color={…}",
            },
            "notification": {
                "name": "notification",
                "import_from": "antd",
                "props_hint": "notification.open({…})",
            },
            "typography": {
                "name": "Typography",
                "import_from": "antd",
                "props_hint": "Typography.Title, Typography.Text, Typography.Paragraph",
            },
            "layout": {
                "name": "Layout",
                "import_from": "antd",
                "props_hint": "Layout, Layout.Header, Layout.Sider, Layout.Content",
            },
            "menu": {
                "name": "Menu",
                "import_from": "antd",
                "props_hint": "items={…} mode='inline'",
            },
            "form": {
                "name": "Form",
                "import_from": "antd",
                "props_hint": "Form, Form.Item",
            },
            "space": {
                "name": "Space",
                "import_from": "antd",
                "props_hint": "size='middle'",
            },
            "row": {
                "name": "Row",
                "import_from": "antd",
                "props_hint": "Row, Col gutter={16}",
            },
        },
        "keywords": {
            "btn": "button",
            "cta": "button",
            "action": "button",
            "submit": "button",
            "input": "input",
            "textfield": "input",
            "search": "input",
            "textarea": "textarea",
            "dropdown": "select",
            "picker": "select",
            "option": "select",
            "dialog": "dialog",
            "modal": "modal",
            "popup": "modal",
            "overlay": "modal",
            "avatar": "avatar",
            "profilepic": "avatar",
            "badge": "badge",
            "pill": "tag",
            "chip": "tag",
            "tag": "tag",
            "checkbox": "checkbox",
            "switch": "switch",
            "toggle": "switch",
            "radio": "radio",
            "tab": "tabs",
            "table": "table",
            "divider": "divider",
            "separator": "divider",
            "hr": "divider",
            "tooltip": "tooltip",
            "hint": "tooltip",
            "progress": "progress",
            "spinner": "progress",
            "loader": "progress",
            "loading": "progress",
            "toast": "notification",
            "notification": "notification",
            "alert": "notification",
            "snackbar": "notification",
            "label": "typography",
            "typography": "typography",
            "text": "typography",
            "heading": "typography",
            "title": "typography",
            "card": "card",
            "tile": "card",
            "panel": "card",
            "container": "layout",
            "menu": "menu",
            "navbar": "menu",
            "sidebar": "menu",
            "navigation": "menu",
            "form": "form",
            "space": "space",
            "stack": "space",
            "flex": "space",
            "row": "row",
            "grid": "row",
            "layout": "layout",
            "header": "layout",
            "footer": "layout",
            "sider": "layout",
            "content": "layout",
        },
        "fallback_element": "div",
        "framework_hint": "react_ts",
    },
    "bootstrap": {
        "components": {
            "button": {
                "name": "button",
                "import_from": "",
                "props_hint": 'class="btn btn-primary" | "btn btn-outline-secondary"',
            },
            "card": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="card" → .card-body, .card-title, .card-text',
            },
            "input": {
                "name": "input",
                "import_from": "",
                "props_hint": 'class="form-control" type="text"',
            },
            "textarea": {
                "name": "textarea",
                "import_from": "",
                "props_hint": 'class="form-control"',
            },
            "select": {
                "name": "select",
                "import_from": "",
                "props_hint": 'class="form-select"',
            },
            "modal": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="modal" + Bootstrap JS data attributes',
            },
            "badge": {
                "name": "span",
                "import_from": "",
                "props_hint": 'class="badge bg-primary"',
            },
            "checkbox": {
                "name": "input",
                "import_from": "",
                "props_hint": 'class="form-check-input" type="checkbox"',
            },
            "switch": {
                "name": "input",
                "import_from": "",
                "props_hint": 'class="form-check-input" type="checkbox" role="switch"',
            },
            "radio": {
                "name": "input",
                "import_from": "",
                "props_hint": 'class="form-check-input" type="radio"',
            },
            "tabs": {
                "name": "ul",
                "import_from": "",
                "props_hint": 'class="nav nav-tabs" + .tab-pane',
            },
            "table": {
                "name": "table",
                "import_from": "",
                "props_hint": 'class="table table-striped"',
            },
            "divider": {
                "name": "hr",
                "import_from": "",
                "props_hint": 'class="my-3"',
            },
            "tooltip": {
                "name": "span",
                "import_from": "",
                "props_hint": 'data-bs-toggle="tooltip" title="…"',
            },
            "progress": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="progress" → .progress-bar',
            },
            "chip": {
                "name": "span",
                "import_from": "",
                "props_hint": 'class="badge rounded-pill bg-secondary"',
            },
            "alert": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="alert alert-primary" role="alert"',
            },
            "navbar": {
                "name": "nav",
                "import_from": "",
                "props_hint": 'class="navbar navbar-expand-lg navbar-light"',
            },
            "container": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="container" | "container-fluid"',
            },
            "grid": {
                "name": "div",
                "import_from": "",
                "props_hint": 'class="row" → .col-*',
            },
        },
        "keywords": {
            "btn": "button",
            "cta": "button",
            "action": "button",
            "submit": "button",
            "input": "input",
            "textfield": "input",
            "search": "input",
            "textarea": "textarea",
            "dropdown": "select",
            "picker": "select",
            "option": "select",
            "dialog": "modal",
            "modal": "modal",
            "popup": "modal",
            "overlay": "modal",
            "badge": "badge",
            "pill": "chip",
            "chip": "chip",
            "tag": "chip",
            "checkbox": "checkbox",
            "switch": "switch",
            "toggle": "switch",
            "radio": "radio",
            "tab": "tabs",
            "table": "table",
            "divider": "divider",
            "separator": "divider",
            "hr": "divider",
            "tooltip": "tooltip",
            "hint": "tooltip",
            "progress": "progress",
            "spinner": "progress",
            "loader": "progress",
            "loading": "progress",
            "card": "card",
            "tile": "card",
            "panel": "card",
            "container": "container",
            "navbar": "navbar",
            "nav": "navbar",
            "header": "navbar",
            "footer": "container",
            "grid": "grid",
            "row": "grid",
            "col": "grid",
            "alert": "alert",
            "toast": "alert",
            "notification": "alert",
        },
        "fallback_element": "div",
        "framework_hint": "html",
    },
}

_SUPPORTED_LIBRARIES: List[str] = sorted(_LIBRARY_MAPS.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_supported_libraries() -> List[str]:
    """Return sorted list of supported component library names."""
    return list(_SUPPORTED_LIBRARIES)


def get_library_info(library: str) -> Optional[Dict[str, Any]]:
    """Return the full mapping table for a library, or None."""
    if not library:
        return None
    return _LIBRARY_MAPS.get(library.lower())


def map_component(
    library: str,
    element_type: str,
    element_name: str = "",
) -> Dict[str, Any]:
    """Map a Figma element to a library-specific component.

    Resolution order:
    1. Exact match on ``element_type`` (e.g. ``"button"``)
    2. Keyword match on ``element_name`` (e.g. ``"Submit Button"`` → ``button``)
    3. Fallback element for the library

    Returns a dict with keys:
    ``component`` — component or HTML tag name
    ``import_from`` — module to import from (empty string for Bootstrap)
    ``props_hint`` — props / class suggestion for the AI prompt
    ``match_type`` — ``"exact"``, ``"keyword"``, or ``"fallback"``
    """
    lib = get_library_info(library)
    if not lib:
        return {
            "component": "div",
            "import_from": "",
            "props_hint": "",
            "match_type": "unknown_library",
        }

    components = lib["components"]
    keywords = lib["keywords"]
    fallback = lib["fallback_element"]

    # 1. Exact type match
    if element_type and element_type.lower() in components:
        info = components[element_type.lower()]
        return {
            "component": info["name"],
            "import_from": info["import_from"],
            "props_hint": info["props_hint"],
            "match_type": "exact",
        }

    # 2. Keyword match on name
    if element_name:
        name_lower = element_name.lower().replace(" ", "_").replace("-", "_")
        for keyword, mapped_type in keywords.items():
            if keyword in name_lower:
                info = components.get(mapped_type)
                if info:
                    return {
                        "component": info["name"],
                        "import_from": info["import_from"],
                        "props_hint": info["props_hint"],
                        "match_type": "keyword",
                    }

        # Try individual words
        for word in name_lower.split("_"):
            if word in keywords:
                mapped_type = keywords[word]
                info = components.get(mapped_type)
                if info:
                    return {
                        "component": info["name"],
                        "import_from": info["import_from"],
                        "props_hint": info["props_hint"],
                        "match_type": "keyword",
                    }

    # 3. Fallback
    return {
        "component": fallback,
        "import_from": "",
        "props_hint": "",
        "match_type": "fallback",
    }


def get_library_instructions(library: str, framework: str = "") -> str:
    """Return prompt instructions telling the AI to use a component library."""
    lib = get_library_info(library)
    if not lib:
        return ""

    lines = [
        f"COMPONENT LIBRARY: {library}",
        "",
        f"You MUST use {library} components for ALL UI elements.",
        "Import every component from its specified module.",
        "Do NOT render raw HTML elements when a library equivalent exists.",
        "",
        "Library component reference:",
    ]

    comps = lib["components"]
    for key, info in sorted(comps.items()):
        import_path = info["import_from"]
        if import_path:
            lines.append(f"  - {info['name']}  →  import from '{import_path}'")
        else:
            lines.append(f"  - {info['name']}  →  {info['props_hint']}")

    return "\n".join(lines)


def get_library_dependencies(library: str) -> Dict[str, str]:
    """Return the ``dependencies`` entry for ``package.json``."""
    if not library:
        return {}
    deps: Dict[str, str] = {
        "shadcn": {
            "@radix-ui/react-dialog": "^1.0.5",
            "@radix-ui/react-dropdown-menu": "^2.0.6",
            "@radix-ui/react-select": "^2.0.0",
            "@radix-ui/react-tabs": "^1.0.4",
            "@radix-ui/react-tooltip": "^1.0.7",
            "@radix-ui/react-checkbox": "^1.0.4",
            "@radix-ui/react-switch": "^1.0.3",
            "@radix-ui/react-radio-group": "^1.1.3",
            "@radix-ui/react-avatar": "^1.0.4",
            "@radix-ui/react-toast": "^1.1.5",
            "@radix-ui/react-separator": "^1.0.3",
            "@radix-ui/react-progress": "^1.0.3",
            "@radix-ui/react-label": "^2.0.2",
            "class-variance-authority": "^0.7.0",
            "clsx": "^2.1.0",
            "tailwind-merge": "^2.2.0",
            "lucide-react": "^0.344.0",
        },
        "mui": {
            "@mui/material": "^5.15.0",
            "@emotion/react": "^11.11.3",
            "@emotion/styled": "^11.11.0",
            "@mui/icons-material": "^5.15.0",
        },
        "antd": {
            "antd": "^5.12.0",
            "@ant-design/icons": "^5.2.6",
        },
        "bootstrap": {
            "bootstrap": "^5.3.2",
        },
    }
    return deps.get(library.lower(), {})

# Figma Data Format Reference

## Frame Data Structure

Each frame in the input JSON has this structure:

```json
{
  "frame": {
    "id": "1:2",
    "name": "Desktop - 1",
    "width": 1440,
    "height": 900
  },
  "elements": [...],
  "images": {...},
  "styles": {...},
  "interactions": {...}
}
```

## Element Properties

### Base Element
```json
{
  "id": "2:3",
  "name": "Button",
  "type": "FRAME",
  "x": 100,
  "y": 200,
  "width": 120,
  "height": 48
}
```

### Style Properties
```json
{
  "fills": [
    {
      "type": "SOLID",
      "color": { "r": 0.2, "g": 0.4, "b": 0.8 },
      "opacity": 1.0
    }
  ],
  "strokes": [...],
  "effects": [...],
  "text": {
    "fontFamily": "Inter",
    "fontSize": 16,
    "fontWeight": 500,
    "color": { "r": 1, "g": 1, "b": 1 },
    "textAlignHorizontal": "CENTER"
  },
  "cornerRadius": 8,
  "padding": { "top": 12, "right": 24, "bottom": 12, "left": 24 }
}
```

### Text Elements
```json
{
  "id": "3:4",
  "name": "Title",
  "type": "TEXT",
  "content": "Hello World",
  "fills": [
    {
      "type": "SOLID",
      "color": { "r": 0.1, "g": 0.1, "b": 0.1 }
    }
  ],
  "text": {
    "fontFamily": "Inter",
    "fontSize": 24,
    "fontWeight": 700
  }
}
```

### Image Elements
```json
{
  "id": "4:5",
  "name": "Hero Image",
  "type": "RECTANGLE",
  "fills": [
    {
      "type": "IMAGE",
      "imageRef": "abc123"
    }
  ]
}
```

### Component Instances
```json
{
  "id": "5:6",
  "name": "Primary Button",
  "type": "INSTANCE",
  "componentId": "1:7",
  "overrides": {
    "2:8": {
      "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0.5, "b": 1}}]
    }
  }
}
```

## Color Conversion

Figma uses 0-1 range for RGB values. Convert to CSS:
```javascript
const toHex = (r, g, b) => {
  const to255 = (v) => Math.round(v * 255);
  return `#${to255(r).toString(16).padStart(2, '0')}${to255(g).toString(16).padStart(2, '0')}${to255(b).toString(16).padStart(2, '0')}`;
};

// Example: {r: 0.2, g: 0.4, b: 0.8} → #3366cc
```

## Layout Types

- `FRAME` → Container (flex or grid)
- `GROUP` → Grouping without visual impact
- `COMPONENT` → Reusable component definition
- `INSTANCE` → Instance of a component
- `TEXT` → Text content
- `RECTANGLE` → Shape (often images)
- `ELLIPSE` → Circle/oval
- `VECTOR` → SVG path
- `LINE` → Line element

## Constraints

- `constraints.horizontal`: `LEFT`, `RIGHT`, `CENTER`, `STRETCH`, `SCALE`
- `constraints.vertical`: `TOP`, `BOTTOM`, `CENTER`, `STRETCH`, `SCALE`

## Auto Layout

- `layoutMode`: `HORIZONTAL`, `vertical`, `NONE`
- `itemSpacing`: Gap between items
- `paddingLeft/Right/Top/Bottom`: Internal padding
- `primaryAxisAlignItems`: `MIN`, `CENTER`, `MAX`, `SPACE_BETWEEN`
- `counterAxisAlignItems`: `MIN`, `CENTER`, `MAX`

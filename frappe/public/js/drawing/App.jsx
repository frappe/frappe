import * as React from "react";
import { Excalidraw, exportToSvg } from "@excalidraw/excalidraw";

export function App() {
  const [excalidrawAPI, setExcalidrawAPI] = React.useState(null);

  React.useEffect(() => {
    if (!excalidrawAPI) {
      return;
    }

    if (cur_frm.doc.editor_state) {
      excalidrawAPI.updateScene({
        elements: JSON.parse(cur_frm.doc.editor_state),
      });
    }
  }, [excalidrawAPI]);

  return (
    <div>
      <button
        className="btn btn-secondary"
        onClick={async () => {
          if (!excalidrawAPI) {
            return;
          }
          const svg = await exportToSvg({
            appState: {
              exportBackground: false,
            },
            elements: excalidrawAPI.getSceneElements(),
          });

          //
          const elements = JSON.stringify(excalidrawAPI.getSceneElements());
          cur_frm.set_value("editor_state", elements);

          cur_frm.get_field("svg_preview").$wrapper.html(svg.outerHTML);
          cur_frm.set_value("svg", svg.outerHTML);
          cur_frm.save();
        }}
      >
        Save SVG
      </button>

      <div style={{ height: "500px" }}>
        <Excalidraw
          excalidrawAPI={(api) => setExcalidrawAPI(api)}
          ref={(api) => setExcalidrawAPI(api)}
        />
      </div>
    </div>
  );
}

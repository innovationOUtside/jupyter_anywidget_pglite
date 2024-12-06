
// To toggle indicator
// StatusIndicatorService.getInstance().toggleButtonAppearance();

class StatusIndicatorService {
  private static instance: StatusIndicatorService;
  private button: ToolbarButton | null = null;

  private constructor() {}

  static getInstance() {
    if (!StatusIndicatorService.instance) {
      StatusIndicatorService.instance = new StatusIndicatorService();
    }
    return StatusIndicatorService.instance;
  }

  setButton(button: ToolbarButton) {
    this.button = button;
  }

  toggleButtonAppearance() {
    if (this.button) {
      const isActive = this.button.node.classList.contains('pg-status-active');
      if (isActive) {
        this.button.node.classList.remove("pg-status-active");
        this.button.node.classList.add("pg-status-inactive");
      } else {
        this.button.node.classList.remove("pg-status-inactive");
        this.button.node.classList.add("pg-status-active");
      }
    }
  }
}

//export default StatusIndicatorService;

import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
} from "@jupyterlab/application";

import { IToolbarWidgetRegistry } from "@jupyterlab/apputils";

import { ToolbarButton } from "@jupyterlab/apputils";

const plugin: JupyterFrontEndPlugin<void> = {
  id: "status-indicator:plugin",
  autoStart: true,
  requires: [IToolbarWidgetRegistry],
  activate: (app: JupyterFrontEnd, toolbar: IToolbarWidgetRegistry) => {
    const button = new ToolbarButton({
      className: "jp-StatusIndicator",
      onClick: () => {
        console.log("Status Indicator clicked");
        StatusIndicatorService.getInstance().toggleButtonAppearance();
      },
      tooltip: "Processing Status",
    });

    StatusIndicatorService.getInstance().setButton(button);

    toolbar.addFactory("Notebook", "statusIndicator", (panel) => {
      return button;
    });
  },
};

export default { plugin };
const users = [
  { name: "NN User", initials: "NN", color: "#2855FF" },
  { name: "User 02", initials: "02", color: "#D6FF00" },
  { name: "User 03", initials: "03", color: "#111111" },
  { name: "Guest User", initials: "GU", color: "#F05252" }
];

const columns = ["Backlog", "Todo", "In Progress", "Review", "Done"];

let tasks = [
  {
    id: "api-task",
    title: "API Task",
    description: "Define optimistic updates, retry states, and visible event confirmations for board movement.",
    column: "In Progress",
    assignee: "NN User",
    badges: ["LIVE", "EDITING"],
    state: "editing",
    comments: ["Sync payload is stable.", "Review optimistic movement after drawer edits."],
    history: ["Created in Backlog", "Moved to In Progress by NN User"]
  },
  {
    id: "design-system",
    title: "Design System",
    description: "Refine badge language, glass surfaces, typography rhythm, and status hierarchy.",
    column: "Todo",
    assignee: "User 02",
    badges: ["EDITING"],
    state: "editing",
    comments: ["Keep cobalt as the repeated product signal."],
    history: ["User 02 started editing"]
  },
  {
    id: "websocket-layer",
    title: "WebSocket Layer",
    description: "Simulate conflict detection, lock ownership, and event ordering for shared cards.",
    column: "Review",
    assignee: "User 03",
    badges: ["CONFLICT", "LIVE"],
    state: "conflict",
    comments: ["Conflict detected between reorder and title edit."],
    history: ["Conflict detected in WebSocket Layer"]
  },
  {
    id: "mobile-scroll",
    title: "Mobile Board Scroll",
    description: "Preserve five-column context with controlled horizontal movement on small screens.",
    column: "Backlog",
    assignee: "Guest User",
    badges: ["ONLINE"],
    state: "live",
    comments: ["Tablet width feels balanced."],
    history: ["Guest User opened mobile preview"]
  },
  {
    id: "permissions-model",
    title: "Permissions Model",
    description: "Show locked cards without hiding ownership, reason, or current collaborator.",
    column: "Backlog",
    assignee: "NN User",
    badges: ["LOCKED"],
    state: "locked",
    comments: ["Locked by NN User for schema review."],
    history: ["NN User locked Permissions Model"]
  },
  {
    id: "release-notes",
    title: "Release Notes",
    description: "Write short technical status notes for live product changes.",
    column: "Done",
    assignee: "User 02",
    badges: ["LIVE"],
    state: "live",
    comments: ["Version note drafted."],
    history: ["User 02 completed release notes"]
  }
];

let activities = [
  "NN User moved API Task to Review",
  "User 02 is editing Design System",
  "Conflict detected in WebSocket Layer",
  "Guest User joined realtime-kanban Board"
];

let selectedTaskId = null;
let draggedTaskId = null;
let workspaceBooted = false;

const welcome = document.getElementById("welcome");
const workspace = document.getElementById("workspace");
const enterButton = document.getElementById("enterWorkspace");
const board = document.getElementById("board");
const miniAvatars = document.getElementById("miniAvatars");
const activityFeed = document.getElementById("activityFeed");
const editingNow = document.getElementById("editingNow");
const toastStack = document.getElementById("toastStack");
const drawer = document.getElementById("taskDrawer");
const drawerTitle = document.getElementById("drawerTitle");
const drawerContent = document.getElementById("drawerContent");
const closeDrawer = document.getElementById("closeDrawer");
const lastChanged = document.getElementById("lastChanged");

function initialsFor(name) {
  return users.find((user) => user.name === name)?.initials || "GU";
}

function colorFor(name) {
  return users.find((user) => user.name === name)?.color || "#2855FF";
}

function badgeClass(label) {
  return label.toLowerCase();
}

function renderAvatars() {
  miniAvatars.innerHTML = users
    .map(
      (user) =>
        `<span class="avatar" style="--ring:${user.color}" title="${user.name}">${user.initials}</span>`
    )
    .join("");
}

function renderBoard() {
  board.innerHTML = columns
    .map((column) => {
      const columnTasks = tasks.filter((task) => task.column === column);
      const cards = columnTasks.length
        ? columnTasks.map(renderCard).join("")
        : `<div class="empty-state">Flow</div>`;

      return `
        <article class="column" data-column="${column}">
          <header class="column-header">
            <h3 class="column-title">${column}</h3>
            <span class="column-count">${columnTasks.length}</span>
          </header>
          <div class="card-list">${cards}</div>
        </article>
      `;
    })
    .join("");

  bindCardEvents();
  bindColumnEvents();
}

function renderCard(task) {
  const stateClass = task.state === "conflict" ? "conflict-state" : task.state === "locked" ? "locked-state" : "";
  return `
    <article class="task-card ${stateClass}" draggable="true" data-task-id="${task.id}" tabindex="0" aria-label="${task.title}">
      <div class="card-badges">
        ${task.badges.map((badge) => `<span class="status-badge ${badgeClass(badge)}">${badge}</span>`).join("")}
      </div>
      <div>
        <h3>${task.title}</h3>
        <p>${task.description}</p>
      </div>
      <div class="live-line" aria-hidden="true"></div>
      <div class="card-meta">
        <span class="assignee"><span class="tiny-avatar" style="--ring:${colorFor(task.assignee)}">${initialsFor(task.assignee)}</span>${task.assignee}</span>
        <span class="status-badge ${badgeClass(task.badges[0])}">${task.state.toUpperCase()}</span>
      </div>
    </article>
  `;
}

function bindCardEvents() {
  document.querySelectorAll(".task-card").forEach((card) => {
    card.addEventListener("click", () => openDrawer(card.dataset.taskId));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDrawer(card.dataset.taskId);
      }
    });
    card.addEventListener("dragstart", () => {
      draggedTaskId = card.dataset.taskId;
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      draggedTaskId = null;
      card.classList.remove("dragging");
    });
  });
}

function bindColumnEvents() {
  document.querySelectorAll(".column").forEach((column) => {
    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      column.classList.add("drag-over");
    });
    column.addEventListener("dragleave", () => column.classList.remove("drag-over"));
    column.addEventListener("drop", () => {
      column.classList.remove("drag-over");
      moveTask(draggedTaskId, column.dataset.column, true);
    });
  });
}

function moveTask(taskId, targetColumn, announce = false) {
  const task = tasks.find((item) => item.id === taskId);
  if (!task || task.column === targetColumn) return;

  task.column = targetColumn;
  task.badges = Array.from(new Set(["LIVE", ...task.badges.filter((badge) => badge !== "LOCKED")]));
  if (task.state === "locked") task.state = "live";
  task.history.unshift(`Moved to ${targetColumn} by NN User`);
  addActivity(`NN User moved ${task.title} to ${targetColumn}`);
  renderBoard();
  if (selectedTaskId === taskId) openDrawer(taskId);
  if (announce) showToast(`${task.title} moved to ${targetColumn}`);
}

function renderActivity() {
  activityFeed.innerHTML = activities
    .slice(0, 6)
    .map(
      (activity, index) => `
        <div class="activity-item ${index === 0 ? "new" : ""}">
          <strong>${activity.split(" ").slice(0, 2).join(" ")}</strong>
          <span>${activity}</span>
        </div>
      `
    )
    .join("");

  const editingTasks = tasks.filter((task) => task.badges.includes("EDITING") || task.state === "conflict");
  editingNow.innerHTML = editingTasks
    .slice(0, 3)
    .map(
      (task) => `
        <div class="editing-item">
          <strong>${task.assignee}</strong>
          <span>${task.state === "conflict" ? "Conflict on" : "Editing"} ${task.title}</span>
        </div>
      `
    )
    .join("");
}

function addActivity(message) {
  activities.unshift(message);
  activities = activities.slice(0, 10);
  lastChanged.textContent = "Last change just now";
  renderActivity();
}

function openDrawer(taskId) {
  const task = tasks.find((item) => item.id === taskId);
  if (!task) return;

  selectedTaskId = taskId;
  drawerTitle.textContent = task.title;
  drawerContent.innerHTML = `
    <div class="drawer-block">
      <div class="card-badges">
        ${task.badges.map((badge) => `<span class="status-badge ${badgeClass(badge)}">${badge}</span>`).join("")}
      </div>
      <p>${task.description}</p>
    </div>
    <div class="drawer-block">
      <h4>Collaboration State</h4>
      <div class="drawer-row"><span>Status</span><strong>${task.state.toUpperCase()}</strong></div>
      <div class="drawer-row"><span>Assigned User</span><strong>${task.assignee}</strong></div>
      <div class="drawer-row"><span>Column</span><strong>${task.column}</strong></div>
    </div>
    <div class="drawer-block">
      <h4>Activity History</h4>
      ${task.history.map((item) => `<p>${item}</p>`).join("")}
    </div>
    <div class="drawer-block">
      <h4>Comments</h4>
      ${task.comments
        .map(
          (comment) => `
            <div class="comment">
              <span class="tiny-avatar" style="--ring:${colorFor(task.assignee)}">${initialsFor(task.assignee)}</span>
              <p>${comment}</p>
            </div>
          `
        )
        .join("")}
    </div>
  `;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeTaskDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `<span>${message}</span>`;
  toastStack.appendChild(toast);
  window.setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    window.setTimeout(() => toast.remove(), 240);
  }, 3600);
}

function randomRealtimeEvent() {
  const eventType = Math.floor(Math.random() * 4);
  const task = tasks[Math.floor(Math.random() * tasks.length)];
  const user = users[Math.floor(Math.random() * users.length)];

  if (eventType === 0) {
    task.assignee = user.name;
    task.state = "editing";
    task.badges = Array.from(new Set(["EDITING", "LIVE", ...task.badges.filter((badge) => badge !== "LOCKED")]));
    task.history.unshift(`${user.name} is editing ${task.title}`);
    addActivity(`${user.name} is editing ${task.title}`);
    showToast(`${user.name} started editing ${task.title}`);
  }

  if (eventType === 1) {
    task.state = "conflict";
    task.badges = Array.from(new Set(["CONFLICT", "LIVE", ...task.badges.filter((badge) => badge !== "LOCKED")]));
    task.history.unshift(`Conflict detected in ${task.title}`);
    addActivity(`Conflict detected in ${task.title}`);
    showToast(`Conflict detected in ${task.title}`);
  }

  if (eventType === 2) {
    task.state = "locked";
    task.badges = Array.from(new Set(["LOCKED", ...task.badges.filter((badge) => badge !== "EDITING")]));
    task.history.unshift(`${user.name} locked ${task.title}`);
    addActivity(`${user.name} locked ${task.title}`);
    showToast(`${task.title} is locked by ${user.name}`);
  }

  if (eventType === 3) {
    const targetColumn = columns[Math.floor(Math.random() * columns.length)];
    task.column = targetColumn;
    task.state = "live";
    task.badges = Array.from(new Set(["LIVE", "ONLINE"]));
    task.history.unshift(`${user.name} moved ${task.title} to ${targetColumn}`);
    addActivity(`${user.name} moved ${task.title} to ${targetColumn}`);
    showToast(`${task.title} moved to ${targetColumn}`);
  }

  renderBoard();
  if (selectedTaskId === task.id) openDrawer(task.id);
}

function bootWorkspace() {
  if (workspaceBooted) return;
  workspaceBooted = true;
  renderAvatars();
  renderBoard();
  renderActivity();

  window.setTimeout(() => showToast("Workspace synced with 4 online users"), 800);
  window.setInterval(randomRealtimeEvent, 6200);
  window.setInterval(() => {
    lastChanged.textContent = `Last change ${Math.floor(Math.random() * 4) + 1}s ago`;
  }, 2600);
}

enterButton.addEventListener("click", () => {
  document.body.classList.add("app-transition");
  window.setTimeout(() => {
    welcome.hidden = true;
    workspace.hidden = false;
    workspace.classList.add("active");
    bootWorkspace();
  }, 520);
});

if (new URLSearchParams(window.location.search).get("workspace") === "1") {
  welcome.hidden = true;
  workspace.hidden = false;
  workspace.classList.add("active");
  bootWorkspace();
}

closeDrawer.addEventListener("click", closeTaskDrawer);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeTaskDrawer();
});

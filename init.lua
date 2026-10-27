local modifiers = {"ctrl", "alt", "shift"}
local panPixels = 60
local types = hs.eventtap.event.types
local props = hs.eventtap.event.properties
local dragTimer  -- keep a reference so it isn't garbage collected

-- A hotkey callback runs while its modifiers are still down. A mouse event
-- created there inherits them, and Control-click is a right-click, so iMovie
-- never begins a left-button drag. Pass {} so the click is a plain left click.
local function postMouse(eventType, point)
  local ev = hs.eventtap.event.newMouseEvent(eventType, point, {})
  if eventType == types.leftMouseDown then
    print("leftMouseDown")
    ev:setProperty(props.mouseEventClickState, 1)
  elseif eventType == types.leftMouseUp then
    print("leftMouseUp")
    ev:setProperty(props.mouseEventClickState, 0)
  end
  ev:post()
end

local function releaseDrag()
  if not dragTimer then return end
  dragTimer:stop()
  dragTimer = nil
  postMouse(types.leftMouseUp, hs.mouse.absolutePosition())
end

-- Drag from one point to another over `steps` small moves
local function dragMouse(from, to, steps, interval)
  steps = steps or 15
  interval = interval or 0.01
  releaseDrag()

  hs.mouse.absolutePosition(from)
  postMouse(types.leftMouseDown, from)

  local i = 0
  dragTimer = hs.timer.doEvery(interval, function()
    i = i + 1
    local t = i / steps
    local p = {
      x = from.x + (to.x - from.x) * t,
      y = from.y + (to.y - from.y) * t,
    }
    if i < steps then
      postMouse(types.leftMouseDragged, p)
    else
      postMouse(types.leftMouseUp, to)
      dragTimer:stop()
      dragTimer = nil
    end
  end)
end

-- Grab whatever is under the pointer and drag it dx, dy pixels.
-- Wait until the keypad has released ctrl-alt-shift before pressing the button.
local function dragBy(dx, dy)
  print(string.format("dragBy %d %d", dx, dy))
  hs.timer.doAfter(0.03, function()
    local p = hs.mouse.absolutePosition()
    dragMouse(p, {x = p.x + dx, y = p.y + dy})
  end)
end

hs.hotkey.bind(modifiers, "left",  function() dragBy(-40, 0) end)
hs.hotkey.bind(modifiers, "right", function() dragBy(40, 0) end)
hs.hotkey.bind(modifiers, "j", function() hs.eventtap.scrollWheel({panPixels, 0}, {}, "pixel") end)
hs.hotkey.bind(modifiers, "k", function() hs.eventtap.scrollWheel({-panPixels, 0}, {}, "pixel") end)

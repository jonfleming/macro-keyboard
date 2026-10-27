local modifiers = {"ctrl", "alt", "shift"}
local panPixels = 60
local dragPixels = 8       -- pointer travel per knob detent
local holdSeconds = 2      -- how long the button stays down after the knob stops
local types = hs.eventtap.event.types
local props = hs.eventtap.event.properties

-- Hammerspoon here is Lua 5.4, which has no ffi module. Mouse events are
-- posted with hs.eventtap. An empty modifier table keeps this a left click:
-- the hotkey's ctrl would otherwise turn it into a right-click.
local buttonDown = false
local releaseTimer
local pendingX, pendingY = 0, 0
local queued = false

local function stamp(msg)
  local ms = math.floor(hs.timer.absoluteTime() / 1e6) % 1000
  print(string.format("%s.%03d %s", os.date("%H:%M:%S"), ms, msg))
end

local function postMouse(eventType, x, y, dx, dy)
  local ev = hs.eventtap.event.newMouseEvent(eventType, {x = x, y = y}, {})
  ev:setProperty(props.mouseEventButtonNumber, 0)
  ev:setProperty(props.mouseEventClickState, 1)
  ev:setProperty(props.mouseEventDeltaX, dx or 0)
  ev:setProperty(props.mouseEventDeltaY, dy or 0)
  ev:post()
  if eventType == types.leftMouseDown then
    stamp("leftMouseDown")
  elseif eventType == types.leftMouseDragged then
    stamp(string.format("leftMouseDragged %d %d", dx or 0, dy or 0))
  elseif eventType == types.leftMouseUp then
    stamp("leftMouseUp")
  end
  -- Let iMovie handle this event before the next one is posted.
  if eventType ~= types.leftMouseUp then
    hs.timer.usleep(20000)
  end
end

local function endDrag()
  releaseTimer = nil
  if not buttonDown then return end
  buttonDown = false
  local p = hs.mouse.absolutePosition()
  postMouse(types.leftMouseUp, p.x, p.y, 0, 0)
end

local function runDrag()
  local dx, dy = pendingX, pendingY
  pendingX, pendingY = 0, 0
  if dx == 0 and dy == 0 then return end

  local from = hs.mouse.absolutePosition()
  if not buttonDown then
    postMouse(types.leftMouseDown, from.x, from.y, 0, 0)
    buttonDown = true
  end

  -- Walk in 2px steps so a detent glides instead of jumping.
  local movedX, movedY = 0, 0
  while movedX ~= dx or movedY ~= dy do
    local remainX, remainY = dx - movedX, dy - movedY
    local sx = math.max(-2, math.min(2, remainX))
    local sy = math.max(-2, math.min(2, remainY))
    movedX, movedY = movedX + sx, movedY + sy
    postMouse(types.leftMouseDragged, from.x + movedX, from.y + movedY, sx, sy)
  end

  if pendingX ~= 0 or pendingY ~= 0 then
    runDrag()
    return
  end
  if releaseTimer then releaseTimer:stop() end
  -- Release only after the knob has been still, so a slow turn stays one drag.
  releaseTimer = hs.timer.doAfter(holdSeconds, endDrag)
end

-- Grab whatever is under the pointer and drag it dx, dy pixels.
-- Wait until the keypad has released ctrl-alt-shift before pressing the button.
local function dragBy(dx, dy)
  stamp(string.format("dragBy %d %d", dx, dy))
  pendingX = pendingX + dx
  pendingY = pendingY + dy
  if releaseTimer then
    releaseTimer:stop()
    releaseTimer = nil
  end
  if queued then return end
  queued = true
  hs.timer.doAfter(0.03, function()
    queued = false
    runDrag()
  end)
end

hs.hotkey.bind(modifiers, "left",  function() dragBy(-dragPixels, 0) end)
hs.hotkey.bind(modifiers, "right", function() dragBy(dragPixels, 0) end)
hs.hotkey.bind(modifiers, "j", function() hs.eventtap.scrollWheel({panPixels, 0}, {}, "pixel") end)
hs.hotkey.bind(modifiers, "k", function() hs.eventtap.scrollWheel({-panPixels, 0}, {}, "pixel") end)

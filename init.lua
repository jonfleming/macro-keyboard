local modifiers = {"ctrl", "alt", "shift"}
local panPixels = 60
local dragPixels = 8       -- slow turn, pixels per detent
local dragPixelsFast = 32  -- fast turn, pixels per detent
local holdSeconds = 2      -- how long the button stays down after the knob stops
local slowGap = 0.15       -- seconds between detents at or above this stay precise
local fastGap = 0.04       -- seconds between detents at or below this use dragPixelsFast
local types = hs.eventtap.event.types
local props = hs.eventtap.event.properties

-- Hammerspoon here is Lua 5.4, which has no ffi module. Mouse events are
-- posted with hs.eventtap. An empty modifier table keeps this a left click:
-- the hotkey's ctrl would otherwise turn it into a right-click.
local buttonDown = false
local releaseTimer
local pendingX, pendingY = 0, 0
local queued = false
local lastDetent = nil
local ticksWaiting = 0

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
  -- Larger steps sleep less so a fast spin does not queue up behind the animation.
  if eventType ~= types.leftMouseUp then
    local mag = math.abs(dx or 0)
    local pause = 20000
    if mag >= 8 then
      pause = 6000
    elseif mag >= 4 then
      pause = 10000
    end
    hs.timer.usleep(pause)
  end
end

local function endDrag()
  releaseTimer = nil
  lastDetent = nil
  ticksWaiting = 0
  if not buttonDown then return end
  buttonDown = false
  local p = hs.mouse.absolutePosition()
  postMouse(types.leftMouseUp, p.x, p.y, 0, 0)
end

-- Windows-style curve: a lone or widely spaced detent stays at dragPixels.
-- Detents that arrive close together, or pile up while a move is in progress,
-- grow toward dragPixelsFast.
local function acceleratedPixels()
  local now = hs.timer.absoluteTime() / 1e9
  local gap = slowGap
  if lastDetent then
    gap = now - lastDetent
  end
  lastDetent = now
  ticksWaiting = ticksWaiting + 1

  local tGap = 0
  if gap < slowGap then
    tGap = math.min(1, (slowGap - gap) / (slowGap - fastGap))
  end
  local tQueue = math.min(1, math.max(0, ticksWaiting - 1) / 3)
  local t = math.max(tGap, tQueue)
  t = t * t
  return math.floor(dragPixels + (dragPixelsFast - dragPixels) * t + 0.5)
end

local function takeStep(remain)
  local mag = math.abs(remain)
  local cap = 2
  if mag >= 24 then
    cap = 8
  elseif mag >= 12 then
    cap = 4
  end
  if remain < 0 then
    return math.max(-cap, remain)
  end
  return math.min(cap, remain)
end

local function runDrag()
  local dx, dy = pendingX, pendingY
  pendingX, pendingY = 0, 0
  ticksWaiting = 0
  if dx == 0 and dy == 0 then return end

  local from = hs.mouse.absolutePosition()
  if not buttonDown then
    postMouse(types.leftMouseDown, from.x, from.y, 0, 0)
    buttonDown = true
  end

  -- Small moves glide 2px at a time. A fast burst takes larger steps so it keeps up.
  local movedX, movedY = 0, 0
  while movedX ~= dx or movedY ~= dy do
    local sx = takeStep(dx - movedX)
    local sy = takeStep(dy - movedY)
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
local function dragBy(dirX, dirY)
  local pixels = acceleratedPixels()
  local dx, dy = dirX * pixels, dirY * pixels
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

hs.hotkey.bind(modifiers, "left",  function() dragBy(-1, 0) end)
hs.hotkey.bind(modifiers, "right", function() dragBy(1, 0) end)

-- The keypad cannot mix a click with a key. This chord clicks, then sends
-- the Mac Delete key (USB backspace) once ctrl-alt-shift has been released.
hs.hotkey.bind(modifiers, "delete", function()
  hs.timer.doAfter(0.03, function()
    local p = hs.mouse.absolutePosition()
    local down = hs.eventtap.event.newMouseEvent(types.leftMouseDown, p, {})
    down:setProperty(props.mouseEventClickState, 1)
    down:post()
    hs.timer.usleep(20000)
    local up = hs.eventtap.event.newMouseEvent(types.leftMouseUp, p, {})
    up:setProperty(props.mouseEventClickState, 1)
    up:post()
    hs.timer.usleep(30000)
    hs.eventtap.keyStroke({}, "delete", 0)
  end)
end)
hs.hotkey.bind(modifiers, "j", function() hs.eventtap.scrollWheel({panPixels, 0}, {}, "pixel") end)
hs.hotkey.bind(modifiers, "k", function() hs.eventtap.scrollWheel({-panPixels, 0}, {}, "pixel") end)

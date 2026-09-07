extends Node2D

const VIEW_W := 1280.0
const VIEW_H := 720.0
const GROUND_Y := 572.0
const FELIX_X := 242.0
const FELIX_SCALE := 0.82
const GRAVITY := 2700.0
const JUMP_SPEED := -990.0
const MAX_FALL_SPEED := 1780.0
const COYOTE_TIME := 0.10
const JUMP_BUFFER := 0.11
const HOUSE_MODE_DURATION := 6.4

var felix: AnimatedSprite2D
var felix_y := 0.0
var felix_vy := 0.0
var felix_rest_y := 0.0
var on_ground := true
var coyote_left := 0.0
var jump_buffer_left := 0.0

var running := false
var dead := false
var elapsed := 0.0
var distance := 0.0
var world_speed := 500.0
var spawn_timer := 1.5
var obstacles: Array = []
var ground_tiles: Array[Sprite2D] = []
var mid_tiles: Array[Sprite2D] = []
var sparkles: Array = []

var score_label: Label
var best_label: Label
var message_label: Label
var submessage_label: Label
var title_label: Label
var best_distance := 0
var rng := RandomNumberGenerator.new()

var sparkle_tex: Texture2D
var yard_obstacle_textures: Array[Texture2D] = []
var house_obstacle_textures: Array[Texture2D] = []

var far_bg: Sprite2D
var mode := "yard"
var house_mode_left := 0.0
var house_cooldown := 360.0
var interior_notice_left := 0.0

const YARD_FAR := "res://assets/yard_bg_far.svg"
const YARD_MID := "res://assets/yard_bg_mid.svg"
const YARD_GROUND := "res://assets/yard_ground_tile.svg"
const HOUSE_FAR := "res://assets/house_bg_far.svg"
const HOUSE_MID := "res://assets/house_bg_mid.svg"
const HOUSE_GROUND := "res://assets/house_ground_tile.svg"

func _ready() -> void:
    rng.randomize()
    get_viewport().set_embedding_subwindows(false)
    _build_world()
    _reset_run(false)

func _build_world() -> void:
    far_bg = Sprite2D.new()
    far_bg.position = Vector2(VIEW_W * 0.5, VIEW_H * 0.5)
    far_bg.z_index = -30
    add_child(far_bg)

    for i in range(2):
        var mid := Sprite2D.new()
        mid.position = Vector2(VIEW_W * 0.5 + i * VIEW_W, VIEW_H * 0.5)
        mid.z_index = -20
        add_child(mid)
        mid_tiles.append(mid)

    for i in range(4):
        var tile := Sprite2D.new()
        tile.position = Vector2(256.0 + i * 512.0, 645.0)
        tile.z_index = 2
        add_child(tile)
        ground_tiles.append(tile)

    sparkle_tex = load("res://assets/sparkle.svg")
    yard_obstacle_textures = [
        load("res://assets/obstacle_flower.svg"),
        load("res://assets/obstacle_crystal.svg"),
        load("res://assets/obstacle_lollipop.svg")
    ]
    house_obstacle_textures = [
        load("res://assets/house_obstacle_box.svg"),
        load("res://assets/house_obstacle_stool.svg"),
        load("res://assets/house_obstacle_toy.svg")
    ]

    felix = AnimatedSprite2D.new()
    var frames := SpriteFrames.new()
    frames.add_animation("run")
    frames.set_animation_speed("run", 13.0)
    frames.set_animation_loop("run", true)
    frames.add_frame("run", load("res://assets/felix_run_1.svg"))
    frames.add_frame("run", load("res://assets/felix_run_2.svg"))
    frames.add_frame("run", load("res://assets/felix_run_3.svg"))
    frames.add_frame("run", load("res://assets/felix_run_2.svg"))
    frames.add_animation("jump")
    frames.set_animation_speed("jump", 1.0)
    frames.set_animation_loop("jump", true)
    frames.add_frame("jump", load("res://assets/felix_jump.svg"))
    felix.sprite_frames = frames
    felix.scale = Vector2.ONE * FELIX_SCALE
    felix.position.x = FELIX_X
    felix.z_index = 5
    add_child(felix)
    felix.play("run")

    felix_rest_y = GROUND_Y - 126.0 * FELIX_SCALE * 0.5
    _make_ui()
    _apply_environment_visuals("yard")

func _make_ui() -> void:
    title_label = _new_label("RUN FELIX, RUN", 54, Vector2(38, 26), Color("#4a235e"), 8)
    title_label.z_index = 20

    score_label = _new_label("0 m", 34, Vector2(1010, 35), Color("#4a235e"), 6)
    score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    score_label.size = Vector2(220, 50)
    score_label.z_index = 20

    best_label = _new_label("BEST 0 m", 21, Vector2(1030, 82), Color("#6b4d7c"), 4)
    best_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
    best_label.size = Vector2(200, 40)
    best_label.z_index = 20

    message_label = _new_label("TAP TO RUN", 48, Vector2(0, 260), Color("#fff8e7"), 10)
    message_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    message_label.size = Vector2(VIEW_W, 65)
    message_label.z_index = 30

    submessage_label = _new_label("Tap anywhere to jump  •  Felix now runs through pastel neighborhood yards", 24, Vector2(0, 326), Color("#fff8e7"), 6)
    submessage_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    submessage_label.size = Vector2(VIEW_W, 48)
    submessage_label.z_index = 30

func _new_label(text_value: String, font_size: int, pos: Vector2, color: Color, outline: int) -> Label:
    var label := Label.new()
    label.text = text_value
    label.position = pos
    var settings := LabelSettings.new()
    settings.font_size = font_size
    settings.font_color = color
    settings.outline_size = outline
    settings.outline_color = Color("#efb7d1")
    label.label_settings = settings
    add_child(label)
    return label

func _input(event: InputEvent) -> void:
    var pressed := false
    var released := false

    if event.is_action_pressed("jump"):
        pressed = true
    elif event.is_action_released("jump"):
        released = true
    elif event is InputEventScreenTouch:
        pressed = event.pressed
        released = not event.pressed
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
        pressed = event.pressed
        released = not event.pressed

    if pressed:
        if dead:
            _reset_run(true)
            return
        if not running:
            running = true
            message_label.visible = false
            submessage_label.visible = false
        jump_buffer_left = JUMP_BUFFER

    if released and felix_vy < -360.0:
        felix_vy *= 0.58

func _process(delta: float) -> void:
    elapsed += delta
    _update_background(delta)
    _update_sparkles(delta)

    if not running or dead:
        _idle_bob()
        return

    jump_buffer_left = maxf(0.0, jump_buffer_left - delta)
    if on_ground:
        coyote_left = COYOTE_TIME
    else:
        coyote_left = maxf(0.0, coyote_left - delta)

    if jump_buffer_left > 0.0 and coyote_left > 0.0:
        _jump()
        jump_buffer_left = 0.0
        coyote_left = 0.0

    felix_vy = minf(MAX_FALL_SPEED, felix_vy + GRAVITY * delta)
    felix_y += felix_vy * delta

    if felix_y >= felix_rest_y:
        felix_y = felix_rest_y
        felix_vy = 0.0
        on_ground = true
        if felix.animation != "run":
            felix.play("run")
    else:
        on_ground = false
        if felix.animation != "jump":
            felix.play("jump")

    felix.position.y = felix_y

    world_speed = minf(810.0, 500.0 + distance * 0.84)
    distance += world_speed * delta / 100.0
    score_label.text = "%d m" % int(distance)

    if house_cooldown > 0.0:
        house_cooldown -= world_speed * delta / 100.0
    if house_mode_left > 0.0:
        house_mode_left -= delta
        if house_mode_left <= 0.0:
            _leave_house()
    if interior_notice_left > 0.0:
        interior_notice_left -= delta
        if interior_notice_left <= 0.0 and not dead and running:
            message_label.visible = false
            submessage_label.visible = false

    _scroll_ground(delta)
    _update_obstacles(delta)

    spawn_timer -= delta
    if spawn_timer <= 0.0:
        _spawn_obstacle()
        var pace := clampf((world_speed - 500.0) / 310.0, 0.0, 1.0)
        spawn_timer = rng.randf_range(1.25, 2.05) - pace * 0.16
        if mode == "house":
            spawn_timer -= 0.07

    if on_ground and rng.randf() < delta * 11.0:
        _spawn_sparkle(Vector2(FELIX_X - 60.0, felix_y + 42.0), 0.42, 0.65)

    _check_collisions()

func _jump() -> void:
    felix_vy = JUMP_SPEED
    on_ground = false
    felix.play("jump")
    for i in range(5):
        _spawn_sparkle(Vector2(FELIX_X - 40.0 + rng.randf_range(-12.0, 16.0), felix_y + 40.0), rng.randf_range(0.5, 0.9), rng.randf_range(0.55, 0.95))

func _apply_environment_visuals(new_mode: String) -> void:
    mode = new_mode
    if mode == "yard":
        far_bg.texture = load(YARD_FAR)
        for mid in mid_tiles:
            mid.texture = load(YARD_MID)
        for tile in ground_tiles:
            tile.texture = load(YARD_GROUND)
    else:
        far_bg.texture = load(HOUSE_FAR)
        for mid in mid_tiles:
            mid.texture = load(HOUSE_MID)
        for tile in ground_tiles:
            tile.texture = load(HOUSE_GROUND)

func _enter_house() -> void:
    house_mode_left = HOUSE_MODE_DURATION
    _apply_environment_visuals("house")
    for i in range(8):
        _spawn_sparkle(Vector2(FELIX_X + rng.randf_range(-30.0, 50.0), felix_y + rng.randf_range(-40.0, 26.0)), rng.randf_range(0.55, 1.0), rng.randf_range(0.6, 1.05))
    message_label.text = "THROUGH THE WINDOW!"
    submessage_label.text = "Felix is tearing through the house"
    message_label.visible = true
    submessage_label.visible = true
    interior_notice_left = 1.0

func _leave_house() -> void:
    _apply_environment_visuals("yard")
    house_cooldown = 400.0 + rng.randf_range(0.0, 120.0)
    for i in range(8):
        _spawn_sparkle(Vector2(FELIX_X + rng.randf_range(-30.0, 50.0), felix_y + rng.randf_range(-36.0, 22.0)), rng.randf_range(0.55, 1.0), rng.randf_range(0.6, 1.0))
    message_label.text = "BACK OUTSIDE!"
    submessage_label.text = "Pastel yard sprint resumed"
    message_label.visible = true
    submessage_label.visible = true
    interior_notice_left = 0.9

func _update_background(delta: float) -> void:
    var mid_speed := 44.0 if running and not dead else 10.0
    if mode == "house":
        mid_speed = 26.0 if running and not dead else 6.0
    for mid in mid_tiles:
        mid.position.x -= mid_speed * delta
        if mid.position.x <= -VIEW_W * 0.5:
            mid.position.x += VIEW_W * 2.0

func _scroll_ground(delta: float) -> void:
    for tile in ground_tiles:
        tile.position.x -= world_speed * delta
    var rightmost := -10000.0
    for tile in ground_tiles:
        rightmost = maxf(rightmost, tile.position.x)
    for tile in ground_tiles:
        if tile.position.x < -256.0:
            tile.position.x = rightmost + 512.0
            rightmost = tile.position.x

func _spawn_obstacle() -> void:
    if mode == "yard" and house_cooldown <= 0.0 and distance > 60.0 and rng.randf() < 0.22:
        _spawn_house_entry()
        house_cooldown = 99999.0
        return

    if mode == "yard":
        var yard_type: int = rng.randi_range(0, yard_obstacle_textures.size() - 1)
        var yard_scale: float = [0.8, 0.86, 0.88][yard_type]
        var yard_h: float = [150.0, 146.0, 120.0][yard_type] * yard_scale
        var yard_w: float = [104.0, 82.0, 118.0][yard_type] * yard_scale
        _add_simple_obstacle(yard_obstacle_textures[yard_type], yard_w, yard_h, yard_scale, GROUND_Y - yard_h * 0.5 + 3.0, "yard")
    else:
        var house_type: int = rng.randi_range(0, house_obstacle_textures.size() - 1)
        var house_scale: float = [0.86, 0.8, 0.76][house_type]
        var house_h: float = [110.0, 98.0, 92.0][house_type] * house_scale
        var house_w: float = [104.0, 90.0, 96.0][house_type] * house_scale
        _add_simple_obstacle(house_obstacle_textures[house_type], house_w, house_h, house_scale, GROUND_Y - house_h * 0.5 + 2.0, "house")

func _add_simple_obstacle(texture: Texture2D, w: float, h: float, scale_value: float, y_pos: float, env: String) -> void:
    var sprite := Sprite2D.new()
    sprite.texture = texture
    sprite.position = Vector2(VIEW_W + 110.0, y_pos)
    sprite.scale = Vector2.ONE * scale_value
    sprite.z_index = 4
    add_child(sprite)
    obstacles.append({
        "kind": "normal",
        "sprite": sprite,
        "w": w,
        "h": h * 0.84,
        "env": env
    })

func _spawn_house_entry() -> void:
    var sprite := Sprite2D.new()
    sprite.texture = load("res://assets/house_entry.svg")
    sprite.position = Vector2(VIEW_W + 170.0, 430.0)
    sprite.scale = Vector2.ONE * 1.0
    sprite.z_index = 3
    add_child(sprite)
    obstacles.append({
        "kind": "house_entry",
        "sprite": sprite,
        "entered": false,
        "w": 250.0,
        "h": 250.0,
        "opening": Rect2(-38.0, -72.0, 92.0, 100.0),
        "solid_top": Rect2(-125.0, -128.0, 250.0, 56.0),
        "solid_bottom": Rect2(-125.0, 28.0, 250.0, 100.0),
        "solid_left": Rect2(-125.0, -72.0, 70.0, 100.0),
        "solid_right": Rect2(54.0, -72.0, 71.0, 100.0)
    })

func _update_obstacles(delta: float) -> void:
    for i in range(obstacles.size() - 1, -1, -1):
        var ob = obstacles[i]
        var sprite: Sprite2D = ob["sprite"]
        sprite.position.x -= world_speed * delta
        if ob["kind"] == "normal":
            sprite.rotation = sin(elapsed * 3.0 + float(i)) * 0.012
        else:
            sprite.rotation = 0.0
            var opening: Rect2 = ob["opening"]
            var window_rect := Rect2(sprite.position.x + opening.position.x, sprite.position.y + opening.position.y, opening.size.x, opening.size.y)
            if not bool(ob["entered"]) and _felix_rect().intersects(window_rect):
                ob["entered"] = true
                obstacles[i] = ob
            if sprite.position.x < FELIX_X - 170.0 and bool(ob["entered"]):
                sprite.queue_free()
                obstacles.remove_at(i)
                _enter_house()
                continue
        if sprite.position.x < -260.0:
            sprite.queue_free()
            obstacles.remove_at(i)

func _felix_rect() -> Rect2:
    return Rect2(FELIX_X - 42.0, felix_y - 42.0, 84.0, 82.0)

func _check_collisions() -> void:
    var f_rect := _felix_rect()
    for ob in obstacles:
        var sprite: Sprite2D = ob["sprite"]
        if ob["kind"] == "house_entry":
            var top_local: Rect2 = ob["solid_top"]
            var bottom_local: Rect2 = ob["solid_bottom"]
            var left_local: Rect2 = ob["solid_left"]
            var right_local: Rect2 = ob["solid_right"]
            var top_rect := Rect2(sprite.position.x + top_local.position.x, sprite.position.y + top_local.position.y, top_local.size.x, top_local.size.y)
            var bottom_rect := Rect2(sprite.position.x + bottom_local.position.x, sprite.position.y + bottom_local.position.y, bottom_local.size.x, bottom_local.size.y)
            var left_rect := Rect2(sprite.position.x + left_local.position.x, sprite.position.y + left_local.position.y, left_local.size.x, left_local.size.y)
            var right_rect := Rect2(sprite.position.x + right_local.position.x, sprite.position.y + right_local.position.y, right_local.size.x, right_local.size.y)
            if f_rect.intersects(top_rect) or f_rect.intersects(bottom_rect) or f_rect.intersects(left_rect) or f_rect.intersects(right_rect):
                _game_over()
                return
        else:
            var w: float = ob["w"]
            var h: float = ob["h"]
            var o_rect := Rect2(sprite.position.x - w * 0.5, sprite.position.y - h * 0.5, w, h)
            if f_rect.intersects(o_rect):
                _game_over()
                return

func _game_over() -> void:
    dead = true
    running = false
    felix.stop()
    if int(distance) > best_distance:
        best_distance = int(distance)
        best_label.text = "BEST %d m" % best_distance
    message_label.text = "OOPS, FELIX!"
    submessage_label.text = "Tap to run again"
    message_label.visible = true
    submessage_label.visible = true
    for i in range(12):
        _spawn_sparkle(Vector2(FELIX_X + rng.randf_range(-35.0, 35.0), felix_y + rng.randf_range(-35.0, 35.0)), rng.randf_range(0.6, 1.1), rng.randf_range(0.65, 1.05))

func _reset_run(start_immediately: bool) -> void:
    for ob in obstacles:
        var sprite: Sprite2D = ob["sprite"]
        sprite.queue_free()
    obstacles.clear()
    distance = 0.0
    world_speed = 500.0
    spawn_timer = 1.45
    dead = false
    running = start_immediately
    on_ground = true
    felix_vy = 0.0
    felix_y = felix_rest_y
    house_mode_left = 0.0
    house_cooldown = 330.0
    interior_notice_left = 0.0
    _apply_environment_visuals("yard")
    felix.position = Vector2(FELIX_X, felix_y)
    felix.play("run")
    score_label.text = "0 m"
    message_label.text = "TAP TO RUN"
    submessage_label.text = "Tap anywhere to jump  •  Jump through open windows when houses appear"
    message_label.visible = not start_immediately
    submessage_label.visible = not start_immediately

func _idle_bob() -> void:
    if dead:
        return
    felix.position.y = felix_rest_y + sin(elapsed * 3.1) * 3.5

func _spawn_sparkle(pos: Vector2, scale_value: float, life: float) -> void:
    var sprite := Sprite2D.new()
    sprite.texture = sparkle_tex
    sprite.position = pos
    sprite.scale = Vector2.ONE * scale_value
    sprite.rotation = rng.randf_range(0.0, TAU)
    sprite.modulate.a = 0.95
    sprite.z_index = 7
    add_child(sprite)
    sparkles.append({
        "sprite": sprite,
        "life": life,
        "max_life": life,
        "vx": rng.randf_range(-110.0, -35.0),
        "vy": rng.randf_range(-95.0, 20.0),
        "spin": rng.randf_range(-4.0, 4.0)
    })

func _update_sparkles(delta: float) -> void:
    for i in range(sparkles.size() - 1, -1, -1):
        var p = sparkles[i]
        var sprite: Sprite2D = p["sprite"]
        p["life"] = float(p["life"]) - delta
        sprite.position.x += float(p["vx"]) * delta
        sprite.position.y += float(p["vy"]) * delta
        p["vy"] = float(p["vy"]) + 180.0 * delta
        sprite.rotation += float(p["spin"]) * delta
        sprite.modulate.a = clampf(float(p["life"]) / float(p["max_life"]), 0.0, 1.0)
        if float(p["life"]) <= 0.0:
            sprite.queue_free()
            sparkles.remove_at(i)

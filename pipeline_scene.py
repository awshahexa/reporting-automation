from manim import *

config.pixel_width = 1280
config.pixel_height = 720
config.frame_rate = 30

BOX_W = 1.8
BOX_H = 0.7
SMALL_BOX_W = 2.0
SMALL_BOX_H = 0.65
WIDE_BOX_W = 2.4
FONT_SZ = 22
SMALL_FONT = 18
SUB_FONT = 14
GREEN = "#48bb78"
RED = "#ef4444"
BLUE = "#3b82f6"
AMBER = "#f59e0b"
DARK_BG = "#0f172a"
CARD_BG = "#1e293b"
CARD_BORDER = "#334155"
LIGHT_TEXT = "#e2e8f0"
MUTED = "#94a3b8"
WHITE = "#ffffff"


def make_box(
    label, sub=",", w=BOX_W, h=BOX_H, fill=CARD_BG, border=CARD_BORDER, font_sz=FONT_SZ
):
    rect = RoundedRectangle(
        width=w, height=h, corner_radius=0.08, fill_color=fill, fill_opacity=1,
        stroke_color=border, stroke_width=2
    )
    txt = Text(label, font_size=font_sz, color=LIGHT_TEXT, font="Segoe UI")
    sub_txt = Text(sub, font_size=SUB_FONT, color=MUTED, font="Segoe UI")
    txt.move_to(rect.get_center())
    sub_txt.next_to(txt, DOWN, buff=0.06)
    return VGroup(rect, txt, sub_txt)


def make_arrow(from_edge, to_edge, color=BLUE, stroke=3):
    return Arrow(from_edge, to_edge, color=color, stroke_width=stroke, buff=0.15)


class PipelineScene(Scene):
    def construct(self):
        self.camera.background_color = DARK_BG

        # ── Title ──
        title = Text(
            "Document Control Pipeline",
            font_size=32, color=WHITE, font="Segoe UI"
        )
        subtitle = Text(
            "Quality Verification & Approval Flow",
            font_size=16, color=MUTED, font="Segoe UI"
        )
        title_group = VGroup(title, subtitle).arrange(DOWN, buff=0.08)
        title_group.to_edge(UP, buff=0.3)
        self.play(Write(title), run_time=0.8)
        self.play(Write(subtitle), run_time=0.5)
        self.wait(0.5)

        # ── Stage 1: Hot Folder ──
        hot = make_box("HOT FOLDER", "Files land here")
        hot.move_to([-5.5, 0.3, 0])
        hot_label = Text("①", font_size=20, color=BLUE, font="Segoe UI")
        hot_label.next_to(hot, UP, buff=0.1)

        self.play(Create(hot), Write(hot_label), run_time=0.6)
        self.wait(0.3)

        # Animate a file dropping into hot folder
        file_rect = RoundedRectangle(
            width=0.25, height=0.15, corner_radius=0.02,
            fill_color=GREEN, fill_opacity=1, stroke_width=0
        )
        file_rect.move_to(hot.get_center() + UP * 1.0)
        self.play(file_rect.animate.move_to(hot.get_center()), run_time=0.5)
        self.play(FadeOut(file_rect, scale=0.5), run_time=0.2)

        # Pulse the hot folder
        self.play(hot[0].animate.set_stroke_color(GREEN), run_time=0.3)
        self.play(hot[0].animate.set_stroke_color(CARD_BORDER), run_time=0.3)
        self.wait(0.3)

        # ── Stage 2: Quality Verification ──
        verify = make_box("QUALITY VERIFY", "OCR, Blur, Content, Signature", w=WIDE_BOX_W)
        verify.move_to([-2.0, 0.3, 0])

        arrow_hv = make_arrow(hot.get_right(), verify.get_left())
        self.play(Create(arrow_hv), run_time=0.4)
        self.play(Create(verify), run_time=0.6)
        self.wait(0.3)

        # Show rules running
        rules = ["Has Text", "File Naming", "Blur Detection", "Content Rules", "Signature Check"]
        rules_group = VGroup()
        for i, rule in enumerate(rules):
            dot = Dot(radius=0.04, color=MUTED)
            txt = Text(rule, font_size=SUB_FONT, color=MUTED, font="Segoe UI")
            row = VGroup(dot, txt).arrange(RIGHT, buff=0.12, aligned_edge=LEFT)
            rules_group.add(row)
        rules_group.arrange(DOWN, buff=0.08, aligned_edge=LEFT)
        rules_group.next_to(verify, UP, buff=0.2)
        rules_group.shift(RIGHT * 0.3)

        # Create the rules text
        self.play(FadeIn(rules_group, shift=LEFT * 0.2), run_time=0.4)

        # Animate each rule turning green
        for i, row in enumerate(rules_group):
            dot, txt = row
            self.play(
                dot.animate.set_color(GREEN),
                txt.animate.set_color(GREEN),
                run_time=0.25
            )
            if i < len(rules_group) - 1:
                self.wait(0.2)

        self.wait(0.4)

        # Flash verify box amber then green (all checks passed)
        self.play(verify[0].animate.set_stroke_color(AMBER), run_time=0.2)
        self.play(verify[0].animate.set_stroke_color(GREEN), run_time=0.2)

        # ── Stage 3: Pass/Fail branch ──
        # Fail branch (down)
        failed = make_box("_FAILED", "Review + re-submit", w=SMALL_BOX_W, h=SMALL_BOX_H, font_sz=SMALL_FONT)
        failed.move_to([-2.0, -1.3, 0])
        arrow_fail = Arrow(
            verify.get_bottom() + LEFT * 0.3,
            failed.get_top(),
            color=RED, stroke_width=3, buff=0.1
        )
        fail_label = Text("FAIL", font_size=16, color=RED, font="Segoe UI")
        fail_label.next_to(arrow_fail, LEFT, buff=0.1)

        self.play(Create(arrow_fail), Write(fail_label), run_time=0.4)
        self.play(Create(failed), run_time=0.5)
        # Pulse failed box red
        self.play(failed[0].animate.set_stroke_color(RED), run_time=0.2)
        self.play(failed[0].animate.set_stroke_color(CARD_BORDER), run_time=0.2)

        # Pass branch (right, from verify to submit)
        submit = make_box("SUBMIT", "Staged by doc type")
        submit.move_to([3.0, 0.3, 0])

        arrow_pass = Arrow(
            verify.get_right(),
            submit.get_left(),
            color=GREEN, stroke_width=3, buff=0.1
        )
        pass_label = Text("PASS", font_size=16, color=GREEN, font="Segoe UI")
        pass_label.next_to(arrow_pass, UP, buff=0.05)

        self.play(Create(arrow_pass), Write(pass_label), run_time=0.4)
        self.play(Create(submit), run_time=0.5)
        self.play(submit[0].animate.set_stroke_color(GREEN), run_time=0.2)
        self.play(submit[0].animate.set_stroke_color(CARD_BORDER), run_time=0.2)

        self.wait(0.3)

        # ── Stage 4: Review → Approve → Archive ──
        review = make_box("REVIEW", "Site / Milestone folders", font_sz=SMALL_FONT, w=SMALL_BOX_W, h=SMALL_BOX_H)
        review.move_to([1.2, -2.0, 0])

        approve = make_box("APPROVE", "PMO one-shot move", font_sz=SMALL_FONT, w=SMALL_BOX_W, h=SMALL_BOX_H)
        approve.move_to([3.5, -2.0, 0])

        archive = make_box("ARCHIVE", "Auto archive cycle", font_sz=SMALL_FONT, w=SMALL_BOX_W, h=SMALL_BOX_H)
        archive.move_to([5.8, -2.0, 0])

        # Arrow from Submit to Review (down-right)
        arrow_sr = Arrow(
            submit.get_bottom() + LEFT * 0.3,
            review.get_top(),
            color=BLUE, stroke_width=3, buff=0.1
        )

        self.play(Create(arrow_sr), run_time=0.4)
        self.play(Create(review), run_time=0.5)

        # Arrow Review → Approve
        arrow_ra = Arrow(
            review.get_right(),
            approve.get_left(),
            color=BLUE, stroke_width=3, buff=0.1
        )
        self.play(Create(arrow_ra), run_time=0.4)
        self.play(Create(approve), run_time=0.5)
        self.play(approve[0].animate.set_stroke_color(GREEN), run_time=0.2)

        # Arrow Approve → Archive
        arrow_aa = Arrow(
            approve.get_right(),
            archive.get_left(),
            color=BLUE, stroke_width=3, buff=0.1
        )
        self.play(Create(arrow_aa), run_time=0.4)
        self.play(Create(archive), run_time=0.5)
        self.play(archive[0].animate.set_stroke_color(AMBER), run_time=0.2)

        self.wait(0.5)

        # ── Footer status ──
        footer = Text(
            "File processed  |  Quality verified  |  Passed → Submit/[DocType]/",
            font_size=14, color=MUTED, font="Segoe UI"
        )
        footer.to_edge(DOWN, buff=0.25)
        self.play(Write(footer), run_time=0.6)

        # ── Final pulse across pipeline ──
        groups = [hot, verify, submit, review, approve, archive]
        for g in groups:
            self.play(g[0].animate.set_stroke_color(GREEN), run_time=0.08)
            self.play(g[0].animate.set_stroke_color(CARD_BORDER), run_time=0.08)

        self.wait(2.0)

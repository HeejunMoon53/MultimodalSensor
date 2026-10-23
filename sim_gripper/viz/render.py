"""MuJoCo 프레임 → mp4."""
import imageio.v2 as imageio


def save_mp4(frames, path, fps=30):
    if not frames:
        return
    with imageio.get_writer(str(path), fps=fps, codec="libx264", quality=7) as w:
        for f in frames:
            w.append_data(f)

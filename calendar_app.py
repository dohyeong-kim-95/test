"""저장된 OOTD 사진을 달력으로 보여주는 웹페이지."""
import calendar
from datetime import date
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, send_from_directory, url_for

STYLE = """
<style>
  body { font-family: sans-serif; margin: 16px; background: #fafafa; color: #222; }
  a { color: inherit; }
  table { border-collapse: collapse; width: 100%; table-layout: fixed; }
  th, td { border: 1px solid #ddd; vertical-align: top; padding: 4px; }
  td { height: 140px; background: #fff; }
  td img { width: 100%; height: 110px; object-fit: cover; }
  .photos { display: flex; flex-wrap: wrap; gap: 12px; }
  .photos div { text-align: center; }
  .photos img { height: 360px; }
</style>
"""

MONTH_HTML = STYLE + """
<h2>
  <a href="{{ url_for('month', year=prev[0], month=prev[1]) }}">&lt;</a>
  {{ year }}년 {{ month }}월
  <a href="{{ url_for('month', year=next[0], month=next[1]) }}">&gt;</a>
</h2>
<table>
  <tr>{% for d in '월화수목금토일' %}<th>{{ d }}</th>{% endfor %}</tr>
  {% for week in weeks %}<tr>
    {% for day in week %}<td>
      {% if day.month == month %}
        <a href="{{ url_for('day', d=day.isoformat()) }}">{{ day.day }}</a>
        {% if thumbs.get(day) %}
          <a href="{{ url_for('day', d=day.isoformat()) }}"><img src="{{ url_for('photo', path=thumbs[day]) }}"></a>
        {% endif %}
      {% endif %}
    </td>{% endfor %}
  </tr>{% endfor %}
</table>
"""

DAY_HTML = STYLE + """
<h2><a href="{{ url_for('month', year=d.year, month=d.month) }}">&lt; 달력</a> {{ d }}</h2>
<div class="photos">
  {% for p in photos %}<div>
    <img src="{{ url_for('photo', path=p) }}"><br>
    {{ p.split('/')[-1][:2] }}:{{ p.split('/')[-1][2:4] }}
    <form method="post" action="{{ url_for('delete', path=p) }}" onsubmit="return confirm('삭제할까요?')">
      <button>삭제</button>
    </form>
  </div>{% else %}<p>사진이 없습니다.</p>{% endfor %}
</div>
"""


def create_app(photo_dir):
    root = Path(photo_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)

    def day_photos(d):
        folder = root / d.isoformat()
        return sorted(f"{d.isoformat()}/{p.name}" for p in folder.glob("*.jpg")) if folder.is_dir() else []

    @app.route("/")
    def index():
        today = date.today()
        return redirect(url_for("month", year=today.year, month=today.month))

    @app.route("/<int:year>/<int:month>")
    def month(year, month):
        if not 1 <= month <= 12:
            abort(404)
        weeks = calendar.Calendar().monthdatescalendar(year, month)
        thumbs = {}
        for week in weeks:
            for d in week:
                photos = day_photos(d)
                if photos:
                    thumbs[d] = photos[-1]
        prev = (year - 1, 12) if month == 1 else (year, month - 1)
        next = (year + 1, 1) if month == 12 else (year, month + 1)
        return render_template_string(
            MONTH_HTML, year=year, month=month, weeks=weeks, thumbs=thumbs, prev=prev, next=next
        )

    @app.route("/day/<d>")
    def day(d):
        try:
            d = date.fromisoformat(d)
        except ValueError:
            abort(404)
        return render_template_string(DAY_HTML, d=d, photos=day_photos(d))

    @app.route("/photos/<path:path>")
    def photo(path):
        return send_from_directory(root, path)

    @app.route("/delete/<path:path>", methods=["POST"])
    def delete(path):
        target = (root / path).resolve()
        if root not in target.parents or target.suffix != ".jpg" or not target.is_file():
            abort(404)
        target.unlink()
        return redirect(url_for("day", d=target.parent.name))

    return app

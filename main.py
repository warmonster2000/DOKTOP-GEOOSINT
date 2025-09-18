from flask import Flask, render_template, request
import exifread
from geopy.geocoders import Nominatim
import os
from werkzeug.utils import secure_filename
import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Создаем папку для загрузок
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def analyze_photo_exif(file_path):
    """Анализ EXIF данных фото"""
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        
        info = {
            'device': 'Неизвестно',
            'photo_time': 'Неизвестно',
            'gps': None,
            'make': 'Неизвестно',
            'model': 'Неизвестно'
        }
        
        # Информация об устройстве
        if 'Image Make' in tags:
            info['make'] = str(tags['Image Make'])
        if 'Image Model' in tags:
            info['model'] = str(tags['Image Model'])
        if info['make'] != 'Неизвестно' or info['model'] != 'Неизвестно':
            info['device'] = f"{info['make']} {info['model']}".strip()
        
        # Время съемки
        if 'EXIF DateTimeOriginal' in tags:
            info['photo_time'] = str(tags['EXIF DateTimeOriginal'])
        elif 'Image DateTime' in tags:
            info['photo_time'] = str(tags['Image DateTime'])
        
        # GPS координаты
        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
            try:
                lat_ref = str(tags.get('GPS GPSLatitudeRef', 'N'))
                lon_ref = str(tags.get('GPS GPSLongitudeRef', 'E'))
                
                lat = tags['GPS GPSLatitude']
                lon = tags['GPS GPSLongitude']
                
                # Конвертация координат в десятичный формат
                lat_decimal = float(lat.values[0].num) / float(lat.values[0].den)
                lon_decimal = float(lon.values[0].num) / float(lon.values[0].den)
                
                if lat_ref == 'S':
                    lat_decimal = -lat_decimal
                if lon_ref == 'W':
                    lon_decimal = -lon_decimal
                
                info['gps'] = (lat_decimal, lon_decimal)
            except:
                info['gps'] = None
        
        return info
        
    except Exception as e:
        print(f"Ошибка анализа EXIF: {e}")
        return None

def get_address_from_coords(lat, lon):
    """Получение адреса по координатам"""
    try:
        geolocator = Nominatim(user_agent="geo_osint_app")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=10)
        
        if location and location.raw:
            address = location.raw.get('address', {})
            return {
                'country': address.get('country', 'Неизвестно'),
                'city': address.get('city') or address.get('town') or 
                       address.get('village') or address.get('suburb', 'Неизвестно'),
                'address': location.address
            }
    except Exception as e:
        print(f"Ошибка геолокации: {e}")
    
    return {'country': 'Неизвестно', 'city': 'Неизвестно', 'address': 'Неизвестно'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'photo' not in request.files:
        return render_template('index.html', error='Файл не выбран')
    
    file = request.files['photo']
    if file.filename == '':
        return render_template('index.html', error='Файл не выбран')
    
    if file:
        try:
            # Сохраняем файл
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Анализируем EXIF
            exif_info = analyze_photo_exif(file_path)
            
            if not exif_info:
                return render_template('index.html', error='Не удалось проанализировать фото')
            
            # Получаем информацию о местоположении
            location_info = {'country': 'Неизвестно', 'city': 'Неизвестно', 'address': 'Неизвестно'}
            if exif_info['gps']:
                location_info = get_address_from_coords(exif_info['gps'][0], exif_info['gps'][1])
            
            # Форматируем время
            photo_time = exif_info.get('photo_time', 'Неизвестно')
            if photo_time != 'Неизвестно':
                try:
                    # Пытаемся преобразовать в читаемый формат
                    photo_time = photo_time.replace(':', '-', 2)
                except:
                    pass
            
            # Удаляем временный файл
            os.remove(file_path)
            
            return render_template('result.html',
                                 country=location_info['country'],
                                 city=location_info['city'],
                                 address=location_info['address'],
                                 device=exif_info['device'],
                                 photo_time=photo_time,
                                 make=exif_info['make'],
                                 model=exif_info['model'])
            
        except Exception as e:
            print(f"Ошибка обработки: {e}")
            return render_template('index.html', error=f'Ошибка обработки: {str(e)}')
    
    return render_template('index.html', error='Неизвестная ошибка')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

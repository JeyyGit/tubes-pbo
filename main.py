
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from tabulate import tabulate
import datetime as dt
import numpy as np
import requests
import mariadb
import locale
import csv
import os


class Aplikasi:
	def __init__(self) -> None:
		locale.setlocale(locale.LC_ALL, 'id_ID')
		self.conn = mariadb.connect(
			user='root',
			password='',
			host='localhost',
			database='pbo_db',
			autocommit=True
		)
		self.cur = self.conn.cursor()
		self.HEADER = '\033[95m'
		self.OKBLUE = '\033[94m'
		self.CYAN = '\033[96m'
		self.OKGREEN = '\033[92m'
		self.WARNING = '\033[93m'
		self.FAIL = '\033[91m'
		self.ENDC = '\033[0m'
		self.BOLD = '\033[1m'
		self.UNDERLINE = '\033[4m'

	def scrape_harga(self, url: str) -> list:
		page = requests.get(url)
		soup = BeautifulSoup(page.content, 'html.parser')
		section = soup.find_all('div', class_='row space30')[-1]
		tables = section.find_all('table')[1:]

		data = []
		for table in tables:
			rows = table.find_all('tr')
			for row in rows:
				cells = row.find_all('td')
				cells_list = []
				for cell in cells:
					cells_list.append(cell.get_text())
				if len(cells_list) > 1 and cells_list[0] != 'Waktu' and cells_list[-1] != '\xa0':
					data.append(cells_list)

		return data

	def scrape_harga_lm(self, url: str) -> dict:
		page = requests.get(url)
		soup = BeautifulSoup(page.content, 'html.parser')
		
		section = soup.find('div', class_='col-md-8')
		table = section.find_all('tr', style='text-align: right;')

		update_section = section.find_all('tr', style='vertical-align: top;')[-1]
		updates = update_section.find_all('td')
		[br.replace_with('\n') for br in updates[0].find_all('br')]

		data = {
			'gram': [],
			'atm_btg': [],
			'atm_gram': [],
			'pgd_btg': [],
			'pgd_gram': [],
			'up_atm': updates[0].get_text().strip().replace('\n ', '\n').replace('(', f'({self.FAIL}').replace(')', f'{self.ENDC})'),
			'up_pgd': updates[1].get_text().strip(),
		}

		for row in table:
			cells = row.find_all('td')
			for i, cell in enumerate(cells):
				text = cell.get_text().replace('(', f'({self.FAIL}').replace(')', f'{self.ENDC})')
				if i == 0:
					data['gram'].append(text)
				elif i == 1:
					data['atm_btg'].append(text)
				elif i == 2:
					data['atm_gram'].append(text)
				elif i == 3:
					data['pgd_btg'].append(text)
				elif i == 4:
					data['pgd_gram'].append(text)

		return data

	def convert_to_literal(self, data: list) -> list:
		def try_convert(inp):
			try:
				return locale.atof(inp)
			except ValueError:
				return inp

		new_data = []
		for row in data:
			r = []
			for i in range(len(row)):
				r.append(try_convert(row[i]))
			new_data.append(r)

		return new_data

	def print_table(self, data: list) -> None:
		# pprint(data)
		if len(data[0]) == 5:
			tabel = tabulate(data, headers=['Waktu', 'USD/oz', 'USD/gr', 'Kurs (IDR/USD)', 'IDR/gr'], tablefmt='fancy_grid')
			print(tabel, end='\n\n')
		elif len(data[0]) == 6:
			tabel = tabulate(data, headers=['Tanggal', 'Waktu', 'USD/oz', 'USD/gr', 'Kurs (IDR/USD)', 'IDR/gr'], tablefmt='fancy_grid').split('\n')
			for line in tabel:
				print(line)
			print()

	def print_lm(self, data: dict, bagan: int) -> None:
		if bagan == 1:
			print(f"\n{data['up_atm']}")
			table = {
				'Gram': data['gram'],
				'per Batangan (Rp)': data['atm_btg'],
				'per Gram (Rp)': data['atm_gram']
			}
		elif bagan == 2:
			print(f"\n{data['up_pgd']}")
			table = {
				'Gram': data['gram'],
				'per Batangan (Rp)': data['pgd_btg'],
				'per Gram (Rp)': data['pgd_gram']
			}

		print(tabulate(table, headers='keys', tablefmt='fancy_grid'), end='\n\n')

	def create_url(self, date: str) -> str:
		hari, bulan, tahun = date.split()
		return f'https://harga-emas.org/history-harga/{tahun}/{bulan}/{hari}'

	def get_today_date(self) -> str:
		today = dt.datetime.now().date()
		return self.date_to_str(today)

	def date_to_str(self, date: dt.date) -> str:
		return dt.date.strftime(date, '%d %B %Y')

	def create_statistic(self, data: list) -> list:
		result = [['Rata-rata'], ['Tertinggi'], ['Terendah'], ['Standar deviasi']]

		data = self.convert_to_literal(data)
		if len(data[0]) == 5:
			data = np.array(data).transpose()[1:].astype(float)
		elif len(data[0]) == 6:
			data = np.array(data).transpose()[2:].astype(float)

		fmt = str.maketrans(',.', '.,')
		result[0].extend([f'{el:,.3f}'.translate(fmt) for el in list(np.mean(data, 1))])
		result[1].extend([f'{el:,}'.translate(fmt) for el in list(np.amax(data, 1))])
		result[2].extend([f'{el:,}'.translate(fmt) for el in list(np.amin(data, 1))])
		result[3].extend([f'{el:.3f}'.translate(fmt) for el in list(np.std(data, 1))])
		
		return result

	def print_statistic(self, data: list) -> None:
		print(tabulate(data, headers=['', 'USD/oz', 'USD/gr', 'Kurs (IDR/USD)', 'IDR/gr'], tablefmt='fancy_grid', floatfmt='.3f'), end='\n\n')

	def create_graph(self, data: list, type: int) -> None:
		data = self.convert_to_literal(data)
		if len(data[0]) == 5:
			data = np.array(data).transpose()
			waktu = data[0]
			usdoz, usdgr, kurs, idrgr = data[1:].astype(float)
			xlabel = [w if i % 2 == 0 or i == len(waktu)-1 else ' ' for i, w in enumerate(waktu)]

		elif len(data[0]) == 6:
			data = np.array(data).transpose()
			tgl, waktu = data[:2]
			waktu = [f'{t} {w}' for t, w in zip(tgl, waktu)]
			xlabel = [w if i % 24 == 0 or i == len(waktu)-1 else ' ' for i, w in enumerate(waktu)]
			usdoz, usdgr, kurs, idrgr = data[2:].astype(float)
		
		plt.style.use('ggplot')
		if type == 1:
			title = 'GRAFIK HARGA EMAS USD/oz TERHADAP WAKTU'
			fig = plt.figure(title)

			plt.title(title)
			plt.xlabel('Waktu')
			plt.ylabel('USD/oz')

			plt.plot(waktu, usdoz, label='USD/oz')
			plt.xticks(range(0, len(waktu)), xlabel)

			x = np.arange(len(waktu))
			z = np.polyfit(x, usdoz, 1)
		elif type == 2:
			title = 'GRAFIK HARGA EMAS USD/gr TERHADAP WAKTU'
			fig = plt.figure(title)
			
			plt.title(title)
			plt.xlabel('Waktu')
			plt.ylabel('USD/gr')

			plt.plot(waktu, usdgr, label='USD/gr')
			plt.xticks(range(0, len(waktu)), xlabel)

			x = np.arange(len(waktu))
			z = np.polyfit(x, usdgr, 1)
		elif type == 3:
			title = 'GRAFIK KURS (IDR/USD) TERHADAP WAKTU'
			fig = plt.figure(title)
			
			plt.title(title)
			plt.xlabel('Waktu')
			plt.ylabel('Kurs (IDR/USD)')

			plt.plot(waktu, kurs, label='Kurs (IDR/USD)')
			plt.xticks(range(0, len(waktu)), xlabel)

			x = np.arange(len(waktu))
			z = np.polyfit(x, kurs, 1)
		elif type == 4:
			title = 'GRAFIK HARGA EMAS IDR/gr TERHADAP WAKTU'
			fig = plt.figure(title)
			
			plt.title(title)
			plt.xlabel('Waktu')
			plt.ylabel('IDR/gr')

			plt.plot(waktu, idrgr, label='IDR/gr')
			plt.xticks(range(0, len(waktu)), xlabel)

			x = np.arange(len(waktu))
			z = np.polyfit(x, idrgr, 1)

		p = np.poly1d(z)
		plt.plot(waktu, p(x), '-.', label='Trendline')

		fig.autofmt_xdate()
		plt.legend()
		plt.show()

	def save_csv(self, data: list, filename: str, date: dt.date = None) -> None:
		if len(data[0]) == 5:
			for row in data:
				row.insert(0, dt.date.strftime(date, '%Y-%m-%d'))

		with open(f'{filename}.csv', 'w', newline='') as f:
			write = csv.writer(f, delimiter=';')
			write.writerow(['Tanggal', 'Waktu', 'USD/oz', 'USD/gr', 'Kurs (IDR/USD)', 'IDR/gr'])
			write.writerows(data)

		print(f'{self.OKGREEN}File \'{filename}.csv\' tersimpan!{self.ENDC}\n')

	def save_db(self, data: list, date: dt.date = None) -> int:
		data = self.convert_to_literal(data)
		if date is None:
			i = 0
			for row in data:
				try:
					self.cur.execute('INSERT INTO harga_emas VALUES (?, ?, ?, ?, ?, ?)', (*row,))
					i += 1
				except:
					...
		else:
			i = 0
			for row in data:
				try:
					self.cur.execute('INSERT INTO harga_emas VALUES (?, ?, ?, ?, ?, ?)', (date, *row))
					i += 1
				except:
					...
		print(f'Berhasil memasukkan {i} baris data baru ke dalam database!')
		return i

	def get_db(self, inp: int) -> None:
		self.cur.execute('SELECT * FROM harga_emas ORDER BY tanggal DESC, waktu DESC')
		data = list(self.cur)

		fmt = str.maketrans(',.', '.,')
		conv = [[] for _ in range(len(data))]
		for i, row in enumerate(data):
			for j, cell in enumerate(row):
				if j == 0:
					conv[i].append(dt.date.strftime(cell, '%Y-%m-%d'))
				elif j == 1:
					conv[i].append(f'{str(cell)[:-3]:0>5}')
				elif j == 2:
					conv[i].append(f'{cell:,.2f}'.translate(fmt))
				elif j == 3:
					conv[i].append(f'{cell:,.2f}'.translate(fmt))
				elif j == 4:
					conv[i].append(f'{cell:,.2f}'.translate(fmt))
				elif j == 5:
					conv[i].append(f'{cell:,.2f}'.translate(fmt))

		if inp == 1:
			conv = conv[:10]
		elif inp == 2:
			conv = conv[:100]
		elif inp < 0:
			conv = conv[:inp+100]
		
		return conv
		
	def csv_to_db(self, file: list) -> int:
		data = []
		for row in file:
			data.append(row.decode('utf-8').strip('\n').strip('\r').split(';'))
	
		return self.save_db(data[1:])

	def menu(self) -> None:
		self.clear()
		print(f'{self.WARNING}Pilih opsi :')
		print(f'0. Keluar')
		print('1. Harga emas hari ini')
		print('2. Harga emas di tanggal tertentu')
		print('3. Harga emas seminggu terakhir')
		print('4. Harga emas logam mulia')
		print(f'5. Tampil data dari database{self.ENDC}')

		pilih = int(input(f'{self.OKGREEN}={self.ENDC} '))
		self.clear()
		if pilih == 1:
			self.hari_ini()
		elif pilih == 2:
			print(f'{self.OKBLUE}Input tanggal yang akan di cari')
			print(f'Contoh : `{self.ENDC}{self.OKGREEN}01 Agustus 2020{self.ENDC}{self.OKBLUE}` ({self.ENDC}{self.FAIL}data dimulai dari tanggal 26 Agustus 2013{self.ENDC}{self.OKBLUE}){self.ENDC}')
			hari, bulan, tahun = input(f'{self.OKGREEN}= {self.ENDC}').split()
			self.hari_custom(hari, bulan, tahun)
		elif pilih == 3:
			self.hari_seminggu()
		elif pilih == 4:
			self.menu_harga_lm()
		elif pilih == 5:
			self.menu_db()
		else:
			print('Keluar dari aplikasi...')
			exit()

	def hari_ini(self) -> None:
		today_date = dt.datetime.now().date()
		today_date_str = dt.date.strftime(today_date, '%A %d %B, %Y')
		print(f'{self.HEADER}===== HARGA EMAS HARI INI =====')
		print(f'- {today_date_str}{self.ENDC}\n')

		date = self.get_today_date()
		url = self.create_url(date)

		print('Mengambil data...', end='\r')
		data = self.scrape_harga(url)
		print(f'{self.OKBLUE}Data tersimpan!{self.ENDC}\n')
		
		print(f'{self.WARNING}Pilih opsi :')
		print('0. Kembali')
		print('1. Tampilkan data')
		print('2. Tampilkan statistik data')
		print('3. Buat grafik')
		print('4. Save ke file CSV')
		print(f'5. Save ke database{self.ENDC}')

		pilih = int(input(f'{self.OKGREEN}={self.ENDC} '))
		if pilih == 1:
			self.print_table(data)
			self.hari_ini()
		elif pilih == 2:
			self.print_statistic(self.create_statistic(data))
			self.hari_ini()
		elif pilih == 3:
			self.menu_graph(data, self.hari_ini)
		elif pilih == 4:
			filename = input(f'{self.OKBLUE}Nama file = {self.ENDC}')
			self.save_csv(data, filename, today_date)
			self.hari_ini()
		elif pilih == 5:
			self.save_db(data, today_date)
			self.hari_ini()
		else:
			self.menu()

	def hari_custom(self, hari: str, bulan: str, tahun: str) -> None:
		date = f'{int(hari):02} {bulan.lower().title()} {tahun}'
		date_stated = dt.datetime.strptime(f'{hari} {bulan} {tahun}', '%d %B %Y').date()

		print(f'{self.HEADER}===== HARGA EMAS DI TANGGAL {date.upper()} ====={self.ENDC}\n')

		url = self.create_url(date)

		print('Mengambil data...', end='\r')
		data = self.scrape_harga(url)
		print(f'{self.OKBLUE}Data tersimpan!{self.ENDC}\n')

		print(f'{self.WARNING}Pilih opsi :')
		print('0. Kembali')
		print('1. Tampilkan tabel')
		print('2. Tampilkan statistik data')
		print('3. Buat grafik')
		print('4. Save ke file CSV')
		print(f'5. Save ke database{self.ENDC}')

		pilih = int(input(f'{self.OKGREEN}={self.ENDC} '))
		if pilih == 1:
			self.print_table(data)
			self.hari_custom(hari, bulan, tahun)
		elif pilih == 2:
			self.print_statistic(self.create_statistic(data))
			self.hari_custom(hari, bulan, tahun)
		elif pilih == 3:
			self.menu_graph(data, self.hari_custom, hari, bulan, tahun)
		elif pilih == 4:
			filename = input(f'{self.OKBLUE}Nama file = {self.ENDC}')
			self.save_csv(data, filename, date_stated)
			self.hari_custom(hari, bulan, tahun)
		elif pilih == 5:
			self.save_db(data, date_stated)
			self.hari_custom(hari, bulan, tahun)
		else:
			self.menu()

	def hari_seminggu(self) -> None:
		today_dt = dt.datetime.now()
		week_dates = [(today_dt-dt.timedelta(days=i)).date() for i in range(7)]
		week_dates_str = [self.date_to_str(date) for date in week_dates]
		print(f'{self.HEADER}===== HARGA EMAS SEMINGU TERAKHIR =====')
		print(f'- Dari {week_dates_str[-1]} sampai {week_dates_str[0]}{self.ENDC}\n')

		urls = [self.create_url(date_str) for date_str in week_dates_str]

		print('Mengambil data...', end='\r')
		
		datas = []
		for i, url in enumerate(reversed(urls)):
			data_hari = self.scrape_harga(url)
			for data in data_hari:
				data.insert(0, str(week_dates[6-i]))
			datas += data_hari
			
		print(f'{self.OKBLUE}Data tersimpan!{self.ENDC}\n')
	
		print(f'{self.WARNING}Pilih opsi :')
		print('0. Kembali')
		print('1. Tampilkan tabel')
		print('2. Tampilkan statistik data')
		print('3. Buat grafik')
		print('4. Save ke file CSV')
		print(f'5. Save ke database{self.ENDC}')

		pilih = int(input(f'{self.OKGREEN}={self.ENDC} '))
		if pilih == 1:
			self.print_table(datas)
			self.hari_seminggu()
		elif pilih == 2:
			self.print_statistic(self.create_statistic(datas))
			self.hari_seminggu()
		elif pilih == 3:
			self.menu_graph(datas, self.hari_seminggu)
		elif pilih == 4:
			filename = input(f'{self.OKBLUE}Nama file = {self.ENDC}')
			self.save_csv(datas, filename)
			self.hari_seminggu()
		elif pilih == 5:
			self.save_db(datas)
			self.hari_seminggu()
		else:
			self.menu()

	def menu_graph(self, data: list, meth, *args: str) -> None:
		self.clear()

		print(f'{self.WARNING}Pilih opsi graf:')
		print('0. Kembali')
		print('1. USD/oz')
		print('2. USD/gr')
		print('3. Kurs (IDR/USD)')
		print(f'4. IDR/gr{self.ENDC}')
		inp = int(input(f'{self.OKGREEN}={self.ENDC} '))

		if inp == 0:
			meth(*args)
		else:
			print('\nMenampilkan grafik...', end='\r')
			self.create_graph(data, inp)
			self.menu_graph(data, meth, *args)

	def menu_harga_lm(self) -> None:
		print(f'{self.HEADER}===== HARGA EMAS LOGAM MULIA ====={self.ENDC}\n')

		date = self.get_today_date()
		url = self.create_url(date)

		print('Mengambil data...', end='\r')
		data = self.scrape_harga_lm(url)
		print(f'{self.OKBLUE}Data tersimpan!{self.ENDC}\n')

		print(f'{self.WARNING}Pilih opsi :')
		print('0. Kembali')
		print('1. Harga emas logam mulia Antam')
		print(f'2. Harga emas logam mulia Pegadaian{self.ENDC}')

		inp = int(input(f'{self.OKGREEN}={self.ENDC} '))
		if inp == 0:
			self.menu()
		else:
			self.print_lm(data, inp)
			self.menu_harga_lm()		

	def menu_db(self) -> None:
		print(f'{self.WARNING}Pilih jumlah data dari database yang ditampilkan:')
		print('0. Kembali')
		print('1. 10')
		print('2. 100')
		print('3. Semua')
		print(f'4. Custom{self.ENDC}')
		inp = int(input(f'{self.OKGREEN}={self.ENDC} '))

		if inp == 0:
			self.menu()
		elif inp == 4:
			inp = int(input(f'Banyak data {self.OKGREEN}={self.ENDC} '))
			self.print_table(self.get_db(inp-100))
			self.menu_db()
		else:
			self.print_table(self.get_db(inp))
			self.menu_db()

	def clear(self) -> None:
		os.system('cls')


class AplikasiAPI(Aplikasi):
	def get_today_data(self) -> dict:
		data = self.scrape_harga(self.create_url(self.get_today_date()))
		
		table = {
			'data': {
				'Waktu': [], 
				'USD/oz': [], 
				'USD/gr': [], 
				'Kurs (IDR/USD)': [], 
				'IDR/gr': []
			},
			'Statistic': {}
		}

		for row in data:
			table['data']['Waktu'].append(row[0])
			table['data']['USD/oz'].append(row[1])
			table['data']['USD/gr'].append(row[2])
			table['data']['Kurs (IDR/USD)'].append(row[3])
			table['data']['IDR/gr'].append(row[4])

		table['Statistic'] = self.get_statistic(self.create_statistic(data))

		return table

	def get_statistic(self, stats: list) -> dict:
		statistic = {
			'USD/oz': {
				'Rata-rata': stats[0][1],
				'Tertinggi': stats[1][1],
				'Terendah': stats[2][1],
				'Standar Deviasi': stats[3][1]
			}, 
			'USD/gr': {
				'Rata-rata': stats[0][2],
				'Tertinggi': stats[1][2],
				'Terendah': stats[2][2],
				'Standar Deviasi': stats[3][2]
			}, 
			'Kurs (IDR/USD)': {
				'Rata-rata': stats[0][3],
				'Tertinggi': stats[1][3],
				'Terendah': stats[2][3],
				'Standar Deviasi': stats[3][3]
			},
			'IDR/gr': {
				'Rata-rata': stats[0][4],
				'Tertinggi': stats[1][4],
				'Terendah': stats[2][4],
				'Standar Deviasi': stats[3][4]
			}
		}

		return statistic

if __name__ == '__main__':
	app = Aplikasi()
	app.menu()
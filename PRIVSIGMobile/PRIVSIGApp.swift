import SwiftUI

@main struct PRIVSIGApp: App {
    @StateObject private var session = Session()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            Group { if session.profile == nil { LoginView() } else { HomeView() } }
                .environmentObject(session).tint(.indigo)
                .onChange(of: phase) { _, value in if value == .active { session.connect() } }
        }
    }
}
struct LoginView: View {
    @EnvironmentObject var session: Session
    @AppStorage("schoolServer") private var server = ""
    @State private var username = ""
    @State private var password = ""
    @State private var error = ""
    @State private var busy = false
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Image(systemName: "graduationcap.fill").font(.system(size: 48)).foregroundStyle(.indigo)
                    Text("PRIVSIG\nTwoja szkoła.\nZawsze przy Tobie.").font(.largeTitle.bold())
                    Text("Uczeń, rodzic i pracownicy korzystają z tego samego serwera szkoły.").foregroundStyle(.secondary)
                    VStack(spacing: 16) {
                        TextField("https://serwer.twojej-szkoly.pl", text: $server).keyboardType(.URL)
                        TextField("Login", text: $username).textContentType(.username)
                        SecureField("Hasło", text: $password).textContentType(.password)
                    }.textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                    if !error.isEmpty { Text(error).foregroundStyle(.red) }
                    Button {
                        busy = true; error = ""
                        Task {
                            do { try await session.login(server: server, username: username, password: password); password = "" }
                            catch { self.error = error.localizedDescription }
                            busy = false
                        }
                    } label: { HStack { Spacer(); if busy { ProgressView() } else { Text("Zaloguj się").bold() }; Spacer() }.padding(8) }
                        .buttonStyle(.borderedProminent).disabled(busy || username.isEmpty || password.isEmpty)
                    Text("Rola i dostęp pochodzą z konta na serwerze. Zmiana roli wymaga uprawnień administratora.").font(.footnote).foregroundStyle(.secondary)
                }.padding(28)
            }.background(Color.indigo.opacity(0.045)).navigationTitle("SCHOOL MOBILE")
        }
    }
}
struct HomeView: View {
    @EnvironmentObject var session: Session
    var body: some View {
        TabView {
            NavigationStack { ResourceView(module: "timetable") }.tabItem { Label("Plan", systemImage: "calendar") }
            NavigationStack {
                List {
                    ForEach(["grades", "attendance", "homework", "assessments", "finals", "notes"], id: \.self) { id in
                        if session.profile?.permissions[id]?.read == true {
                            NavigationLink(Catalog.shared.resource(id).name) { ResourceView(module: id) }
                        }
                    }
                }.navigationTitle("Dziennik")
            }.tabItem { Label("Dziennik", systemImage: "book.closed") }
            NavigationStack { ResourceView(module: "messages") }.tabItem { Label("Wiadomości", systemImage: "bubble.left.and.bubble.right") }
            NavigationStack { AppsView() }.tabItem { Label("Aplikacje", systemImage: "square.grid.2x2") }
            NavigationStack { SettingsView() }.tabItem { Label("Konto", systemImage: "person.crop.circle") }
        }
    }
}
struct AppsView: View {
    @EnvironmentObject var session: Session
    var body: some View {
        List {
            Section {
                Text(session.profile?.school ?? "").font(.headline)
                Text(session.connection).font(.caption).foregroundStyle(.secondary)
            }
            ForEach(Catalog.shared.apps.filter { session.profile?.apps.contains($0.id) == true }) { app in
                NavigationLink {
                    if app.id == "admin" { AdminView() }
                    else if app.id == "reports" { JSONListView(path: "reports", title: "Raporty") }
                    else {
                        List {
                            ForEach(app.modules, id: \.self) { id in
                                if session.profile?.permissions[id]?.read == true {
                                    NavigationLink(Catalog.shared.resource(id).name) { ResourceView(module: id) }
                                }
                            }
                        }.navigationTitle(app.name)
                    }
                } label: { Label(app.name, systemImage: "app.fill").padding(.vertical, 5) }
            }
        }.navigationTitle("Twoje aplikacje")
    }
}
struct ResourceView: View {
    let module: String
    @EnvironmentObject var session: Session
    @State private var rows: [Row] = []
    @State private var error = ""
    @State private var busy = false
    @State private var creating = false
    @State private var filter = "Wszystkie"
    @State private var search = ""
    private var resource: Resource { Catalog.shared.resource(module) }
    private var visible: [Row] {
        let list = rows.filter { row in
            (filter == "Wszystkie" || row.data["day"]?.text == filter) &&
            (search.isEmpty || row.data.values.contains { $0.text.localizedCaseInsensitiveContains(search) })
        }
        guard module == "timetable" else { return list }
        let days = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek"]
        return list.sorted { a, b in
            let da = days.firstIndex(of: a.data["day"]?.text ?? "") ?? 5
            let db = days.firstIndex(of: b.data["day"]?.text ?? "") ?? 5
            return da == db ? (Int(a.data["lesson"]?.text ?? "0") ?? 0) < (Int(b.data["lesson"]?.text ?? "0") ?? 0) : da < db
        }
    }
    var body: some View {
        List {
            if module == "timetable" {
                Section {
                    Picker("Dzień", selection: $filter) {
                        ForEach(["Wszystkie", "Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek"], id: \.self) { Text($0) }
                    }
                    NavigationLink("Zastępstwa") { ResourceView(module: "substitutions") }
                }
            }
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            if busy { ProgressView() }
            if rows.isEmpty && !busy && error.isEmpty { Text("Brak wpisów").foregroundStyle(.secondary) }
            ForEach(visible) { row in
                NavigationLink {
                    RecordDetail(module: module, row: row)
                } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(row.data["subject"]?.text ?? row.data["title"]?.text ?? row.data["name"]?.text ?? resource.name).font(.headline)
                        if module == "grades" { Text((row.data["value"]?.text ?? "") + (row.data["modifier"]?.text ?? "")).font(.title.bold()).foregroundStyle(.indigo) }
                        ForEach(resource.fields.prefix(6)) { f in
                            if let value = row.data[f.key], !value.text.isEmpty { Text("\(f.label): \(value.text)").font(.caption).foregroundStyle(.secondary) }
                        }
                    }.padding(.vertical, 6)
                }
            }
        }.navigationTitle(resource.name).searchable(text: $search)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if session.profile?.permissions[module]?.write == true { Button { creating = true } label: { Image(systemName: "plus") } }
                }
            }
            .sheet(isPresented: $creating) { NavigationStack { RecordEditor(module: module, row: nil) } }
            .task(id: session.revision) { await load() }.refreshable { session.connect(); await load() }
    }
    private func load() async {
        busy = true; error = ""
        do { rows = try await session.request("records/" + module) }
        catch { rows = []; self.error = error.localizedDescription }
        busy = false
    }
}
struct RecordDetail: View {
    let module: String; let row: Row
    @EnvironmentObject var session: Session
    @Environment(\.dismiss) var dismiss
    @State private var editing = false
    @State private var deleting = false
    @State private var error = ""
    var body: some View {
        List {
            ForEach(Catalog.shared.resource(module).fields) { field in
                VStack(alignment: .leading, spacing: 5) { Text(field.label).font(.caption).foregroundStyle(.secondary); Text(row.data[field.key]?.text ?? "—").textSelection(.enabled) }
            }
            NavigationLink("Historia zmian") { JSONListView(path: "records/\(module)/\(row.id)/history", title: "Historia") }
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            if session.profile?.permissions[module]?.write == true {
                Button("Edytuj") { editing = true }
                Button("Usuń", role: .destructive) { deleting = true }
            }
        }.navigationTitle("Szczegóły")
            .sheet(isPresented: $editing, onDismiss: { dismiss() }) { NavigationStack { RecordEditor(module: module, row: row) } }
            .confirmationDialog("Usunąć ten wpis?", isPresented: $deleting) {
                Button("Usuń", role: .destructive) { Task { do { try await session.remove(module, row: row); dismiss() } catch { self.error = error.localizedDescription } } }
            }
    }
}
struct RecordEditor: View {
    let module: String; let row: Row?
    @EnvironmentObject var session: Session
    @Environment(\.dismiss) var dismiss
    @State private var values: [String: String] = [:]
    @State private var choices: [String: [Choice]] = [:]
    @State private var error = ""
    @State private var busy = false
    private var resource: Resource { Catalog.shared.resource(module) }
    var body: some View {
        Form {
            ForEach(resource.fields) { field in
                let binding = Binding<String>(get: { values[field.key] ?? "" }, set: { values[field.key] = $0 })
                if ["student", "class", "user", "book"].contains(field.kind) {
                    Picker(field.label, selection: binding) {
                        Text("Wybierz…").tag("")
                        ForEach(choices[field.key] ?? []) { Text($0.name).tag($0.id) }
                    }
                } else if field.kind == "choice" {
                    Picker(field.label, selection: binding) {
                        if !field.options.contains("") { Text("Wybierz…").tag("") }
                        ForEach(field.options, id: \.self) { Text($0.isEmpty ? "Brak" : $0).tag($0) }
                    }
                } else {
                    TextField(field.label + (field.kind == "date" ? " (YYYY-MM-DD)" : ""), text: binding, axis: field.kind == "long" ? .vertical : .horizontal)
                        .keyboardType(field.kind == "int" ? .numberPad : .default)
                }
            }
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            Text("Zapis przechodzi przez serwer i kontrolę uprawnień. Konflikt zmian wymaga ponownego otwarcia wpisu.").font(.footnote).foregroundStyle(.secondary)
        }.navigationTitle(row == nil ? "Nowy wpis" : "Edytuj wpis")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Anuluj") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Zapisz") { Task { await save() } }.disabled(busy) }
            }.task {
                values = row?.data.mapValues(\.text) ?? [:]
                for field in resource.fields where ["student", "class", "user", "book"].contains(field.kind) {
                    do { choices[field.key] = try await session.options(kind: field.kind) } catch { self.error = error.localizedDescription }
                }
            }
    }
    private func save() async {
        busy = true; error = ""
        do {
            var data: [String: Value] = [:]
            for f in resource.fields {
                let value = values[f.key] ?? ""
                if f.required && value.isEmpty && !(f.kind == "choice" && f.options.contains("")) { throw APIError(status: 0, message: "Uzupełnij: " + f.label) }
                if f.kind == "int" {
                    guard let number = Int(value) else { throw APIError(status: 0, message: "Podaj liczbę: " + f.label) }
                    data[f.key] = .number(Double(number))
                } else { data[f.key] = .string(value) }
            }
            try await session.save(module, row: row, data: data); dismiss()
        } catch { self.error = error.localizedDescription }
        busy = false
    }
}
struct SettingsView: View {
    @EnvironmentObject var session: Session
    var body: some View {
        Form {
            Section("Twoje konto") {
                Text(session.profile?.user.name ?? "")
                Text(Catalog.shared.roles[session.profile?.user.role ?? ""] ?? "")
                Text(session.profile?.school ?? "")
            }
            Section("Synchronizacja") { Text(session.connection); Button("Połącz ponownie") { session.connect() } }
            NavigationLink("Powiadomienia") { JSONListView(path: "notifications", title: "Powiadomienia") }
            Button("Wyloguj", role: .destructive) { Task { await session.logout() } }
            Text("Hasło i token są przechowywane tylko w pamięci aplikacji. Powiadomienia są odczytywane z serwera; to wydanie nie obsługuje push APNs.").font(.footnote).foregroundStyle(.secondary)
        }.navigationTitle("Konto")
    }
}

import SwiftUI

struct AdminView: View {
    var body: some View {
        List {
            NavigationLink("Konta i uprawnienia") { AccountsView() }
            NavigationLink("Szkoły") { SchoolsView() }
            NavigationLink("Dziennik audytowy") { JSONListView(path: "admin/audit", title: "Audyt") }
        }.navigationTitle("Administracja")
    }
}
struct JSONListView: View {
    let path: String; let title: String
    @EnvironmentObject var session: Session
    @State private var rows: [[String: Value]] = []
    @State private var error = ""
    var body: some View {
        List {
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            ForEach(rows.indices, id: \.self) { index in
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(rows[index].keys.sorted(), id: \.self) { key in
                        if !["hash", "prev_hash", "id", "record_id", "actor_id"].contains(key) {
                            Text("\(key): \(rows[index][key]?.text ?? "—")").font(.callout).textSelection(.enabled)
                        }
                    }
                }.padding(.vertical, 6)
            }
            if rows.isEmpty && error.isEmpty { Text("Brak wpisów").foregroundStyle(.secondary) }
        }.navigationTitle(title).task(id: session.revision) { await load() }.refreshable { await load() }
    }
    func load() async {
        do { rows = try await session.request(path); error = "" }
        catch { rows = []; self.error = error.localizedDescription }
    }
}
struct AccountsView: View {
    @EnvironmentObject var session: Session
    @State private var rows: [[String: Value]] = []
    @State private var error = ""
    @State private var create = false
    var body: some View {
        List {
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            ForEach(rows.indices, id: \.self) { i in
                NavigationLink { AccountEditor(existing: rows[i]) } label: {
                    VStack(alignment: .leading) {
                        Text(rows[i]["name"]?.text ?? "Konto")
                        Text(Catalog.shared.roles[rows[i]["role"]?.text ?? ""] ?? "").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }.navigationTitle("Konta").toolbar { Button { create = true } label: { Image(systemName: "plus") } }
            .sheet(isPresented: $create) { NavigationStack { AccountEditor(existing: nil) } }
            .task(id: session.revision) { await load() }.refreshable { await load() }
    }
    func load() async {
        do { rows = try await session.request("admin/users"); error = "" }
        catch { rows = []; self.error = error.localizedDescription }
    }
}
struct AccountEditor: View {
    let existing: [String: Value]?
    @EnvironmentObject var session: Session
    @Environment(\.dismiss) var dismiss
    @State private var username = ""
    @State private var name = ""
    @State private var password = ""
    @State private var role = "student"
    @State private var active = true
    @State private var classIDs: Set<String> = []
    @State private var studentIDs: Set<String> = []
    @State private var disabled: Set<String> = []
    @State private var classes: [Choice] = []
    @State private var students: [Choice] = []
    @State private var error = ""
    @State private var busy = false
    var body: some View {
        Form {
            Section("Konto") {
                if existing == nil { TextField("Login", text: $username).textInputAutocapitalization(.never).autocorrectionDisabled() }
                TextField("Imię i nazwisko", text: $name)
                SecureField(existing == nil ? "Hasło (minimum 12 znaków)" : "Nowe hasło (opcjonalne)", text: $password)
                Picker("Rola", selection: $role) {
                    ForEach(Catalog.shared.roles.keys.sorted(), id: \.self) { key in
                        if key != "superadmin" || session.profile?.user.role == "superadmin" { Text(Catalog.shared.roles[key] ?? key).tag(key) }
                    }
                }
                if existing != nil { Toggle("Konto aktywne", isOn: $active) }
            }
            Section("Przypisane klasy") { ForEach(classes) { option in toggle(option, selection: $classIDs) } }
            Section("Powiązani uczniowie") { ForEach(students) { option in toggle(option, selection: $studentIDs) } }
            Section("Wyłączone aplikacje") {
                ForEach(Catalog.shared.apps) { app in toggle(Choice(id: app.id, name: app.name), selection: $disabled) }
            }
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
        }.navigationTitle(existing == nil ? "Nowe konto" : "Edytuj konto")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Zamknij") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Zapisz") { Task { await save() } }.disabled(busy) }
            }.task {
                if let existing {
                    name = existing["name"]?.text ?? ""; role = existing["role"]?.text ?? "student"
                    if case .bool(let value) = existing["active"] { active = value }
                    classIDs = set(existing["class_ids"]); studentIDs = set(existing["student_ids"]); disabled = set(existing["disabled_apps"])
                }
                do { classes = try await session.options(kind: "class"); students = try await session.options(kind: "student") }
                catch { self.error = error.localizedDescription }
            }
    }
    func toggle(_ option: Choice, selection: Binding<Set<String>>) -> some View {
        Toggle(option.name, isOn: Binding(get: { selection.wrappedValue.contains(option.id) }, set: { enabled in
            if enabled { selection.wrappedValue.insert(option.id) } else { selection.wrappedValue.remove(option.id) }
        }))
    }
    func set(_ value: Value?) -> Set<String> { if case .array(let values) = value { return Set(values.map(\.text)) }; return [] }
    func save() async {
        busy = true; error = ""
        var data: [String: Value] = ["name": .string(name), "role": .string(role), "class_ids": .array(classIDs.sorted().map(Value.string)), "student_ids": .array(studentIDs.sorted().map(Value.string)), "disabled_apps": .array(disabled.sorted().map(Value.string))]
        if existing == nil { data["username"] = .string(username); data["password"] = .string(password) }
        else { data["active"] = .bool(active); if !password.isEmpty { data["password"] = .string(password) } }
        do {
            let id = existing?["id"]?.text
            let _: [String: Value] = try await session.request("admin/users" + (id.map { "/" + $0 } ?? ""), method: id == nil ? "POST" : "PUT", body: data)
            password = ""; session.revision += 1; dismiss()
        } catch { self.error = error.localizedDescription }
        busy = false
    }
}
struct SchoolsView: View {
    @EnvironmentObject var session: Session
    @State private var rows: [[String: Value]] = []
    @State private var name = ""
    @State private var error = ""
    var body: some View {
        List {
            if !error.isEmpty { Text(error).foregroundStyle(.red) }
            ForEach(rows.indices, id: \.self) { i in Text(rows[i]["name"]?.text ?? "Szkoła") }
            if session.profile?.user.role == "superadmin" {
                TextField("Nazwa nowej szkoły", text: $name)
                Button("Utwórz szkołę") { Task {
                    do { let _: [String: Value] = try await session.request("admin/schools", method: "POST", body: ["name": .string(name)]); name = ""; await load() }
                    catch { self.error = error.localizedDescription }
                } }.disabled(name.isEmpty)
            }
        }.navigationTitle("Szkoły").task { await load() }.refreshable { await load() }
    }
    func load() async {
        do { rows = try await session.request("admin/schools"); error = "" } catch { self.error = error.localizedDescription }
    }
}
